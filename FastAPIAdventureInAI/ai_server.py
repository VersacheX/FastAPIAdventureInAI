import asyncio
import uvicorn
import random
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import jwt
from jwt.exceptions import InvalidTokenError

from starlette.concurrency import run_in_threadpool

# Import your AI model setup and logic here
from gptqmodel.models import GPTQModel
from transformers import AutoTokenizer, set_seed

# Load AI settings from database
from ai_settings import get_ai_settings

# Import configuration from environment
from config import CORS_ORIGINS, SECRET_KEY, ALGORITHM

from schemas_ai_server import *

# Load settings once at startup
_AI_SETTINGS = get_ai_settings()
STORYTELLER_PROMPT = _AI_SETTINGS['STORYTELLER_PROMPT']
SUMMARY_SPLIT_MARKER = _AI_SETTINGS['SUMMARY_SPLIT_MARKER']
GAME_DIRECTIVE = _AI_SETTINGS['GAME_DIRECTIVE']
RECENT_MEMORY_LIMIT = _AI_SETTINGS['RECENT_MEMORY_LIMIT']
MEMORY_BACKLOG_LIMIT = _AI_SETTINGS['MEMORY_BACKLOG_LIMIT']
TOKENIZE_HISTORY_CHUNK_SIZE = _AI_SETTINGS['TOKENIZE_HISTORY_CHUNK_SIZE']
TOKENIZED_HISTORY_BLOCK_SIZE = _AI_SETTINGS['TOKENIZED_HISTORY_BLOCK_SIZE']
SUMMARY_MIN_TOKEN_PERCENT = _AI_SETTINGS['SUMMARY_MIN_TOKEN_PERCENT']
MAX_TOKENIZED_HISTORY_BLOCK = _AI_SETTINGS['MAX_TOKENIZED_HISTORY_BLOCK']
MAX_TOKENS = _AI_SETTINGS['MAX_TOKENS']
RESERVED_FOR_GENERATION = _AI_SETTINGS['RESERVED_FOR_GENERATION']
SAFE_PROMPT_LIMIT = _AI_SETTINGS['SAFE_PROMPT_LIMIT']
STOP_TOKENS = _AI_SETTINGS['STOP_TOKENS']

AI_MODEL = "TheBloke/MythoMax-L2-13B-GPTQ"

def silent_model_load():
    import os, contextlib
    with open(os.devnull, 'w') as devnull:
        with contextlib.redirect_stdout(devnull):
            tokenizer = AutoTokenizer.from_pretrained(AI_MODEL, use_fast=True)
            model = GPTQModel.from_quantized(
                AI_MODEL,
                use_exllama=True,
                use_cuda_fp16=True,
                trust_remote_code=True,
                device="cuda:0",
                pad_token_id=50256,
                fuse_layers=True,
                disable_exllama=False,
                disable_exllamav2=False,
                disable_marlin=False,
                disable_machete=False,
                disable_triton=True,
                revision="main"
            )
            return model, tokenizer

STORY_GENERATOR, STORY_TOKENIZER = silent_model_load()

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token from Authorization header"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        return username
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

@app.post("/prime_narrator/")
async def prime_narrator(username: str = Depends(verify_token)):
    inputs = await run_in_threadpool(STORY_TOKENIZER("Prime the narrator.", return_tensors="pt").to("cuda"))
    _ = await run_in_threadpool(
        STORY_GENERATOR.generate,
            **inputs,
            max_new_tokens=1,
            num_return_sequences=1
    )
    return {"status": "primed"}

def flatten_json_prompt(json_data):
    """Build optimized prompt from structured game data."""
    recent_story = json_data.get("RecentStory", [])
    tokenized_history = json_data.get("TokenizedHistory", [])
    deep_memory = json_data.get("DeepMemory")  # Ultra-compressed ancient history

    # Core directives and context
    prompt = (
        f"# Narrator Directives:\n{json_data['NarratorDirectives']}\n\n"
        f"# Universe: {json_data['UniverseName']}\n"
        f"{json_data['UniverseTokens']}\n\n"
        f"# Story Preface:\n{json_data['StoryPreface']}\n\n"
        f"# Player: {json_data['PlayerInfo']['Name']} ({json_data['PlayerInfo']['Gender']})\n"
        f"# Rating: {json_data['GameSettings']['Rating']}\n\n"
    )

    # Deep memory (ultra-compressed ancient history)
    if deep_memory:
        prompt += "# Ancient History (Major Events):\n"
        prompt += f"{deep_memory.strip()}\n\n"

    # Compressed history (if available) - just use the most recent summaries
    if tokenized_history:
        prompt += "# Past Events:\n"
        # Get last N tokenized blocks
        recent_blocks = tokenized_history[-MAX_TOKENIZED_HISTORY_BLOCK:]
        for block in recent_blocks:
            summary = block.get("summary", "").strip()
            if summary:
                prompt += f"{summary}\n\n"

    # Recent chronological story
    prompt += "# Recent Story:\n"
    for entry in recent_story:
        prompt += f"{entry.strip()}\n\n"

    # Current player input
    current_action = json_data['CurrentAction'].strip()
    if current_action:
        action_mode = json_data.get("ActionMode", "ACTION")
        if action_mode == "SPEECH":
            prompt += f"# Player Says: \"{current_action}\"\n\n"
        elif action_mode == "NARRATE":
            prompt += f"# Player Narrative: {current_action}\n\n"
        else:
            prompt += f"# Player Action: {current_action}\n\n"
    else:
        prompt += "# No Player Action. Continue the story naturally.\n\n"

    # Simplified continuation instruction
    prompt += f"{json_data['GameSettings']['StorySplitter']}\n"
    return prompt

@app.post("/generate_story/")
async def generate_story(request: GenerateStoryRequest, username: str = Depends(verify_token)):
    # Set random seed for reproducibility
    set_seed(random.randint(0, 2**32 - 1))

    context = request.context
    user_input = request.user_input or ""
    include_initial = request.include_initial

    # Build prompt (GAME_DIRECTIVE removed - redundant)
    prompt = flatten_json_prompt(context)

    inputs = await run_in_threadpool(STORY_TOKENIZER(prompt, return_tensors="pt").to("cuda"))
    prompt_token_count = inputs.input_ids.shape[-1]

    max_retries = 15
    text = ""
    for attempt in range(1, max_retries + 1):
        output = await run_in_threadpool(STORY_GENERATOR.generate(
                **inputs,
                max_new_tokens=RESERVED_FOR_GENERATION,
                num_return_sequences=1,
                temperature=0.8,
                top_p=0.9,
                repetition_penalty=1.2
            )
        )
        # Decode only the newly generated tokens, not the prompt
        generated_tokens = output[0][prompt_token_count:]
        text = STORY_TOKENIZER.decode(generated_tokens, skip_special_tokens=True)

        # Remove lines starting with any stop token
        for stop_token in STOP_TOKENS:
            if text.strip().startswith(stop_token):
                text = text.strip()[len(stop_token):].lstrip()

        # Remove entire lines containing chapter markers (e.g., "Chapter 1.2.3:" or "1.2.5:" or "1.2:")
        import re
        # Remove lines like "Chapter 1.2.3:" or "Chapter 1.2:"
        text = re.sub(r'^\s*Chapter\s+\d+\.\d+(\.\d+)?:\s*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
        # Remove lines like "1.2.5:" or "1.2:" at the start of a line
        text = re.sub(r'^\s*\d+\.\d+(\.\d+)?:\s*$', '', text, flags=re.MULTILINE)
        # Remove the pattern inline if it appears at the start of the text
        text = re.sub(r'^\s*Chapter\s+\d+\.\d+(\.\d+)?:\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^\s*\d+\.\d+(\.\d+)?:\s*', '', text)
        
        # Remove story splitter if it appears in output
        # if context["GameSettings"]["StorySplitter"] in text:
        #     text = text.split(context["GameSettings"]["StorySplitter"])[-1].strip()
        
        # Remove common prompt artifacts
        text = re.sub(r'#\s*(No player action|Current Player Action|Continue|Recent Story).*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
        text = text.strip()

        if len(text.strip()) > 0:
            break

    return {"story": text.strip()}

@app.post("/generate_from_game/")
async def generate_from_game(request: GenerateFromGameRequest, username: str = Depends(verify_token)):
    """
    Accepts game data directly and builds structured JSON before generating story.
    This endpoint is designed for React clients to call directly.
    """
    # Set random seed for reproducibility
    set_seed(random.randint(0, 2**32 - 1))
    
    # Build structured JSON from game data
    structured_json = {
        "NarratorDirectives": STORYTELLER_PROMPT,
        "UniverseName": request.world_name,
        "UniverseTokens": request.world_tokens,
        "StoryPreface": request.story_preface,
        "GameSettings": {
            "Rating": request.rating_name,
            "StorySplitter": request.story_splitter
        },
        "PlayerInfo": {
            "Name": request.player_name,
            "Gender": request.player_gender
        },
        "DeepMemory": request.deep_memory,
        "TokenizedHistory": request.tokenized_history[-MAX_TOKENIZED_HISTORY_BLOCK:] if request.tokenized_history else [],
        "RecentStory": request.history[-RECENT_MEMORY_LIMIT:] if request.history else [],
        "FullHistory": request.history,
        "CurrentAction": request.user_input,
        "ActionMode": request.action_mode
    }
    
    # Generate story using the structured JSON (GAME_DIRECTIVE removed - redundant)
    prompt = flatten_json_prompt(structured_json)
    
    # Print the full prompt to console
    # print("\n" + "="*80)
    # print("PROMPT BEING SENT TO AI:")
    # print("="*80)
    # print(prompt)
    # print("="*80 + "\n")

    inputs = await run_in_threadpool(STORY_TOKENIZER(prompt, return_tensors="pt").to("cuda"))
    prompt_token_count = inputs.input_ids.shape[-1]
    
    max_retries = 15
    text = ""
    for attempt in range(1, max_retries + 1):
        output = await run_in_threadpool(STORY_GENERATOR.generate(
                **inputs,
                max_new_tokens=RESERVED_FOR_GENERATION,
                num_return_sequences=1,
                temperature=0.8,
                top_p=0.9,
                repetition_penalty=1.2
            )
        )
        # Decode only the newly generated tokens, not the prompt
        generated_tokens = output[0][prompt_token_count:]
        text = STORY_TOKENIZER.decode(generated_tokens, skip_special_tokens=True)

        # Remove lines starting with any stop token
        for stop_token in STOP_TOKENS:
            if text.strip().startswith(stop_token):
                text = text.strip()[len(stop_token):].lstrip()

        # Remove entire lines containing chapter markers (e.g., "Chapter 1.2.3:" or "1.2.5:" or "1.2:")
        import re
        # Remove lines like "Chapter 1.2.3:" or "Chapter 1.2:"
        text = re.sub(r'^\s*Chapter\s+\d+\.\d+(\.\d+)?:\s*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
        # Remove lines like "1.2.5:" or "1.2:" at the start of a line
        text = re.sub(r'^\s*\d+\.\d+(\.\d+)?:\s*$', '', text, flags=re.MULTILINE)
        # Remove the pattern inline if it appears at the start of the text
        text = re.sub(r'^\s*Chapter\s+\d+\.\d+(\.\d+)?:\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^\s*\d+\.\d+(\.\d+)?:\s*', '', text)
        
        # Remove story splitter if it appears in output
        if request.story_splitter in text:
            text = text.split(request.story_splitter)[-1].strip()
        
        # Remove common prompt artifacts
        text = re.sub(r'#\s*(No player action|Current Player Action|Continue|Recent Story).*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
        text = text.strip()

        if len(text.strip()) > 0:
            break

    return {"story": text.strip()}

@app.post("/summarize_chunk/")
async def summarize_chunk(request: SummarizeChunkRequest, username: str = Depends(verify_token)):
    chunk = request.chunk
    max_tokens = request.max_tokens
    previous_summary = request.previous_summary

    # Build context-aware prompt
    prompt_parts = [
        "Condense this story segment into the most efficient summary possible.\n"
        "Include ONLY:\n"
        "  - Major plot events and outcomes\n"
        "  - Character relationship changes\n"
        "  - Critical discoveries, tasks, or missions\n"
        "  - Important character decisions or actions\n"
        "Exclude:\n"
        "  - Character backstories already established\n"
        "  - Atmospheric descriptions\n"
        "  - Dialogue and minor interactions\n"
        "  - Repeated information\n"
        "  - Narrative or analytical commentary\n"
        "Be extremely concise. Use simple, direct language.\n"
        "Only state facts. Do NOT review, interpret, or introduce the segment.\n"
        "Do NOT use phrases like 'This story segment...', 'In this scene...', or any narrative/analysis.\n"
        "Write in bullet points or a single direct sentence. No narrative, review, or analysis.\n"
        "Do not use any symbols or formatting—just plain text.\n"
    ]
    
    # Add previous summary context if available
    if previous_summary:
        prompt_parts.append("\n# Previous Summary (DO NOT repeat this):\n")
        prompt_parts.append(previous_summary)
        prompt_parts.append("\n\n# New Events to Summarize (focus ONLY on what's new):\n")
    else:
        prompt_parts.append("\n# Story Segment:\n")
    
    prompt_parts.append("\n".join(chunk))
    prompt_parts.append(f"\n\n{SUMMARY_SPLIT_MARKER}\n")
    
    prompt = "".join(prompt_parts)
    
    print("\n" + "="*80)
    print("SUMMARIZE_CHUNK - AI PROMPT:")
    print("="*80)
    print(prompt)
    print("="*80 + "\n")
    
    # Single attempt - accept whatever concise summary the AI produces
    inputs = await run_in_threadpool(STORY_TOKENIZER(prompt, return_tensors="pt").to("cuda"))
    summary_output = await run_in_threadpool(STORY_GENERATOR.generate(
            **inputs,
            max_new_tokens=max_tokens,
            num_return_sequences=1,
            temperature=0.6,
            top_p=0.75,
            repetition_penalty=1.1
        )
    )
    summary_text = STORY_TOKENIZER.decode(summary_output[0], skip_special_tokens=True)

    # Strip everything before the marker
    if SUMMARY_SPLIT_MARKER in summary_text:
        summary_text = summary_text.split(SUMMARY_SPLIT_MARKER)[-1]
    
    summary_text = summary_text.strip()
    
    print("\n" + "="*80)
    print("SUMMARIZE_CHUNK - AI RESPONSE (after split marker removal):")
    print("="*80)
    print(summary_text)
    print(f"Token count: {len(STORY_TOKENIZER.encode(summary_text, add_special_tokens=False))}")
    print("="*80 + "\n")

    return {"summary": summary_text}

@app.post("/count_tokens/")
async def count_tokens(request: Request, username: str = Depends(verify_token)):
    """Count tokens in a single text string."""
    import asyncio
    body = await request.json()
    text = body.get("text", "")
    
    tokens = STORY_TOKENIZER.encode(text)
    return {"token_count": len(tokens)}

@app.post("/count_tokens_batch/")
async def count_tokens_batch(request: Request, username: str = Depends(verify_token)):
    """Count tokens for multiple texts."""
    body = await request.json()
    texts = body.get("texts", [])
    
    token_counts = []
    for text in texts:
        tokens = STORY_TOKENIZER.encode(text)
        token_counts.append(len(tokens))
    
    return {"token_counts": token_counts}

if __name__ == "__main__":    
    uvicorn.run(app, host="0.0.0.0", port=9000)