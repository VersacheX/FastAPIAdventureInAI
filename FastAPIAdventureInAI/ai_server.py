import asyncio
import uvicorn
import random
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import re
import jwt
from jwt.exceptions import InvalidTokenError

from starlette.concurrency import run_in_threadpool

# Import your AI model setup and logic here
from gptqmodel.models import GPTQModel
from transformers import AutoTokenizer, set_seed

# Load AI settings from database
from ai.ai_settings import get_ai_settings
from dependencies import get_db, get_current_user

# Import configuration from environment
from config import CORS_ORIGINS, SECRET_KEY, ALGORITHM

from ai.schemas_ai_server import *
from retrieval.describer import describe_entity_ai
from ai.ai_helpers import perform_deep_summarize_chunk


# Helper to get AI settings for a user
def get_user_ai_settings(user_id: int):
    return get_ai_settings(None, None, user_id)

AI_MODEL = "TheBloke/MythoMax-L2-13B-GPTQ"
# AI_MODEL = "TheBloke/LLaMA-30B-GPTQ"
# AI_MODEL = "TheBloke/Mixtral-8x7B-v0.1-GPTQ"

# Alternative Mistral Nemo model options (comment/uncomment to test):
# GPTQ quantized variants (compatible with current GPTQModel.from_quantized loader):
#AI_MODEL = "mistralai/Mistral-Nemo-Instruct-2407"
#AI_MODEL = "bartowski/Mistral-Nemo-Instruct-2407-GPTQ"
#AI_MODEL = "MaziyarPanahi/Mistral-Nemo-Instruct-2407-GPTQ"
#AI_MODEL = "LoneStriker/Mistral-Nemo-Instruct-2407-GPTQ"

def silent_model_load():
    import os, contextlib
    with open(os.devnull, 'w') as devnull:
        with contextlib.redirect_stdout(devnull):
            tokenizer = AutoTokenizer.from_pretrained(AI_MODEL, use_fast=True)
            model = GPTQModel.from_quantized(
                AI_MODEL,
                use_exllamav2=True,
                use_marlin=True,
                use_machete=True,
                use_triton=True,
                use_cuda_fp16=True,
                trust_remote_code=True,
                device="cuda:0",
                pad_token_id=50256,
                fuse_layers=True,
                disable_exllama=False,
                disable_exllamav2=False,
                disable_marlin=False,
                disable_machete=False,
                disable_triton=False,
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
async def prime_narrator(db=Depends(get_db), user=Depends(get_current_user)):
    #settings = get_user_ai_settings(user.id)
    # You can use settings here if needed
    inputs = await run_in_threadpool(lambda: STORY_TOKENIZER("Prime the narrator.", return_tensors="pt").to("cuda"))
    _ = await run_in_threadpool(
        lambda: STORY_GENERATOR.generate(
            **inputs,
            max_new_tokens=1,
            num_return_sequences=1
        )
    )
    return {"status": "primed"}

def flatten_json_prompt(json_data, settings):
    """Build optimized prompt from structured game data with token budget enforcement."""
    recent_story = json_data.get("RecentStory", [])
    tokenized_history = json_data.get("TokenizedHistory", [])
    deep_memory = json_data.get("DeepMemory")  # Ultra-compressed ancient history

    # Core directives and context
    prompt = (
        f"# Narrator Directives:\n{json_data['NarratorDirectives']}\n\n"
        f"# Universe: {json_data['UniverseName']}\n"
        f"{json_data['UniverseTokens']}\n\n"
        #f"# Story Preface:\n{json_data['StoryPreface']}\n\n"
        f"# Player: {json_data['PlayerInfo']['Name']} ({json_data['PlayerInfo']['Gender']})\n"
        f"# Rating: {json_data['GameSettings']['Rating']}\n\n"
    )
    
    # Count tokens in base prompt
    base_tokens = len(STORY_TOKENIZER.encode(prompt))
    #print(f"[Token Budget] Base prompt: {base_tokens} tokens")
    tokens_used = base_tokens
    
    # Reserve tokens for action and continuation
    current_action = json_data['CurrentAction'].strip()
    action_text = ""
    if current_action:
        action_mode = json_data.get("ActionMode", "ACTION")
        if action_mode == "SPEECH":
            action_text = f"# Player Says: \"{current_action}\"\n\n"
        elif action_mode == "NARRATE":
            action_text = f"# Player Narrative: {current_action}\n\n"
        else:
            action_text = f"# Player Action: {current_action}\n\n"
    else:
        action_text = "# No Player Action. Continue the story naturally.\n\n"
    
    action_text += f"{json_data['GameSettings']['StorySplitter']}\n"
    action_tokens = len(STORY_TOKENIZER.encode(action_text))
    #print(f"[Token Budget] Action section: {action_tokens} tokens")
    tokens_used += action_tokens
    
    # Calculate available budget for history
    available_tokens = settings.get("SAFE_PROMPT_LIMIT", 3900) - tokens_used
    
    #print(f"[Token Budget] Available tokens: {available_tokens}")
    # Deep memory (ultra-compressed ancient history)
    if deep_memory and available_tokens > 0:
        deep_section = f"# Ancient History (Major Events):\n{deep_memory.strip()}\n\n"
        deep_tokens = len(STORY_TOKENIZER.encode(deep_section))
        if deep_tokens <= available_tokens:
            prompt += deep_section
            tokens_used += deep_tokens
            available_tokens -= deep_tokens

    total_block_tokens = 0
    # Compressed history (if available) - just use the most recent summaries
    if tokenized_history and available_tokens > 0:
        history_section = "# Past Events:\n"
        # Start with most recent and work backwards until we run out of budget
        recent_blocks = list(reversed(tokenized_history[-settings.get("MAX_TOKENIZED_HISTORY_BLOCK", 4):]))
        blocks_to_include = []       

        for block in recent_blocks:
            summary = block.get("summary", "").strip()
            if summary:
                block_text = f"{summary}\n\n"
                block_tokens = len(STORY_TOKENIZER.encode(block_text))
                if block_tokens <= available_tokens:
                    total_block_tokens += block_tokens
                    blocks_to_include.insert(0, block_text)  # Insert at beginning to maintain order
                    available_tokens -= block_tokens
                else:
                    break  # Stop if we can't fit more
        
        #print(f"[Token Budget] Compressed history tokens:{total_block_tokens}")
        if blocks_to_include:
            prompt += history_section
            for block_text in blocks_to_include:
                prompt += block_text
            tokens_used = settings.get("SAFE_PROMPT_LIMIT", 3900) - available_tokens

    #print(f"[Token Budget] After deep memory and compressed history: {tokens_used} tokens used, {available_tokens} tokens left.")
    
    total_entry_tokens = 0
    # Recent chronological story - also budget constrained
    if recent_story and available_tokens > 0:
        story_section = "# Recent Story:\n"
        # Start with most recent and work backwards
        recent_entries = list(reversed(recent_story))
        entries_to_include = []
        
        for entry in recent_entries:
            entry_text = f"{entry.strip()}\n\n"
            entry_tokens = len(STORY_TOKENIZER.encode(entry_text))
            if entry_tokens <= available_tokens:
                total_entry_tokens += entry_tokens
                entries_to_include.insert(0, entry_text)  # Insert at beginning to maintain order
                available_tokens -= entry_tokens
            else:
                break  # Stop if we can't fit more
        #print(f"[Token Budget] Recent story entries included tokens: {total_entry_tokens}")
        if entries_to_include:
            prompt += story_section
            for entry_text in entries_to_include:
                prompt += entry_text

    # Add action section (already calculated above)
    prompt += action_text
    
    # Log final token count for debugging
    final_tokens = len(STORY_TOKENIZER.encode(prompt))
    print(f"[Token Budget] Final prompt: {final_tokens} tokens (limit: {settings.get('SAFE_PROMPT_LIMIT', 3901) })")
    print(f"[Token Budget] MEMORIES: {total_block_tokens} ACTIONS: {action_tokens} BASE: {base_tokens} RECENT HISTORY: {total_entry_tokens}")
    # if(final_tokens != total_block_tokens + action_tokens + base_tokens + total_entry_tokens):
    #     print(f"Token count mismatch detected! {final_tokens} != {total_block_tokens + action_tokens + base_tokens + total_entry_tokens}")

    return prompt

@app.post("/lore/retrieve_tokens")
async def lore_retrieve_tokens(request: LoreRetrieveRequest, user=Depends(get_current_user)):
    """Retrieve external lore draft tokens based solely on the user lookup prompt.

    Ignores story/world preface intentionally to avoid diluting query focus.
    Non-invasive: does not modify any persistent state. Returns structured draft for user approval.
    """
    lookup_text = request.lookup_prompt.strip()

    desc = await describe_entity_ai(lookup_text, user, STORY_TOKENIZER, STORY_GENERATOR)

    return desc

@app.post("/generate_from_game/")
async def generate_from_game(request: GenerateFromGameRequest, user=Depends(get_current_user)):
    """
    Accepts game data directly and builds structured JSON before generating story.
    This endpoint is designed for React clients to call directly.
    """
    settings = get_user_ai_settings(user.id)
    # Set random seed for reproducibility
    set_seed(random.randint(0, 2**32 - 1))
    
    # Build structured JSON from game data
    structured_json = {
        "NarratorDirectives": settings.get("STORYTELLER_PROMPT", "You're a narrator. Use the world and character information to tell an engaging story."),
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
        "TokenizedHistory": request.tokenized_history[-settings.get("MAX_TOKENIZED_HISTORY_BLOCK", 4):] if request.tokenized_history else [],
        "RecentStory": request.history[-settings.get("RECENT_MEMORY_LIMIT", 600):] if request.history else [],
        "FullHistory": request.history,
        "CurrentAction": request.user_input,
        "ActionMode": request.action_mode
    }
    
    # Generate story using the structured JSON (GAME_DIRECTIVE removed - redundant)
    prompt = flatten_json_prompt(structured_json, settings)
    
    # Print the full prompt to console
    # print("\n" + "="*80)
    # print("PROMPT BEING SENT TO AI:")
    # print("="*80)
    # print(prompt)
    # print("="*80 + "\n")

    inputs = await run_in_threadpool(lambda: STORY_TOKENIZER(prompt, return_tensors="pt").to("cuda"))
    prompt_token_count = inputs.input_ids.shape[-1]
    
    max_retries = 15
    text = ""
    for attempt in range(1, max_retries + 1):
        output = await run_in_threadpool(
            lambda: STORY_GENERATOR.generate(
                **inputs,
                max_new_tokens=settings.get("RESERVED_FOR_GENERATION", 150),
                num_return_sequences=1,
                temperature=0.8,
                top_p=0.6,
                repetition_penalty=1.2
            )
        )
        # Decode only the newly generated tokens, not the prompt
        generated_tokens = output[0][prompt_token_count:]
        text = STORY_TOKENIZER.decode(generated_tokens, skip_special_tokens=True)

        # Remove lines starting with any stop token
        for stop_token in settings.get("STOP_TOKENS", ""):
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

        print(f"OUTPUT:{text}")

    return {"story": text.strip()}

@app.post("/summarize_chunk/")
async def summarize_chunk(request: SummarizeChunkRequest, user=Depends(get_current_user)):
    chunk = request.chunk
    max_tokens = request.max_tokens
    previous_summary = request.previous_summary
    
    settings = get_user_ai_settings(user.id)

    # Build context-aware prompt header
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
        #"Only state facts. Do NOT review, interpret, or introduce the segment.\n"
        #"Do NOT use phrases like 'This story segment...', 'In this scene...', or any narrative/analysis.\n"
        "Write in bullet points or a single direct sentence. No narrative, review, or analysis.\n"
        "Do not use any symbols or formatting—just plain text.\n"
    ]
    
    # Add previous summary context if available
    # if previous_summary:
    #     prompt_parts.append("\n# Previous Summary (DO NOT REPEAT this):\n")
    #     prompt_parts.append(previous_summary)
    #     prompt_parts.append("\n\n# Recent history to Summarize (focus ONLY on what's new):\n")
    # else:
    prompt_parts.append("\n# Story Segment:\n")
    
    # Build the header to count its tokens
    header = "".join(prompt_parts)
    footer = f"\n\n{settings.get('SUMMARY_SPLIT_MARKER', '<<<SPLIT_MARKER>>>')}\n"
    
    header_tokens = len(STORY_TOKENIZER.encode(header))
    footer_tokens = len(STORY_TOKENIZER.encode(footer))
    reserved_tokens = max_tokens  # Reserve space for the summary output
    
    # Calculate available budget for chunk content
    available_tokens = settings.get("SAFE_PROMPT_LIMIT", 3900) - header_tokens - footer_tokens - reserved_tokens
    
    # Add chunk entries until we run out of budget
    chunk_text_parts = []
    for entry in chunk:
        entry_text = entry.strip() + "\n"
        entry_tokens = len(STORY_TOKENIZER.encode(entry_text))
        
        if entry_tokens <= available_tokens:
            chunk_text_parts.append(entry_text)
            available_tokens -= entry_tokens
        else:
            # If we can't fit the whole entry, truncate it
            if len(chunk_text_parts) == 0:
                # At least include a truncated version of the first entry
                words = entry.split()
                truncated = ""
                for word in words:
                    test_text = truncated + " " + word if truncated else word
                    test_tokens = len(STORY_TOKENIZER.encode(test_text))
                    if test_tokens <= available_tokens:
                        truncated = test_text
                    else:
                        break
                if truncated:
                    chunk_text_parts.append(truncated + "...\n")
            break
    
    prompt = header + "".join(chunk_text_parts) + footer
    
    # Log the token count
    final_tokens = len(STORY_TOKENIZER.encode(prompt))
    # print(f"\n[Summarize Token Budget] Prompt: {final_tokens} tokens (limit: {settings.get('SAFE_PROMPT_LIMIT', 3900)})")
    # print(f"[Summarize Token Budget] Chunk entries included: {len(chunk_text_parts)}/{len(chunk)}")
    
    # print("\n" + "="*80)
    # print("SUMMARIZE_CHUNK - AI PROMPT:")
    # print("="*80)
    # print(prompt)
    # print("="*80 + "\n")
    
    # Single attempt - accept whatever concise summary the AI produces
    inputs = await run_in_threadpool(lambda: STORY_TOKENIZER(prompt, return_tensors="pt").to("cuda"))
    summary_output = await run_in_threadpool(
        lambda: STORY_GENERATOR.generate(
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
    if settings.get("SUMMARY_SPLIT_MARKER", "<<<SPLIT_MARKER>>>") in summary_text:
        summary_text = summary_text.split(settings.get("SUMMARY_SPLIT_MARKER", "<<<SPLIT_MARKER>>>"))[-1]

    summary_text = summary_text.strip()
    
    print("\n" + "="*80)
    print("SUMMARIZE_CHUNK - AI RESPONSE (after split marker removal):")
    print("="*80)
    print(summary_text)
    print(f"Token count: {len(STORY_TOKENIZER.encode(summary_text, add_special_tokens=False))}")
    print("="*80 + "\n")

    return {"summary": summary_text}

@app.post("/deep_summarize_chunk/")
async def deep_summarize_chunk(request: DeepSummarizeChunkRequest, user=Depends(get_current_user)):
    return await perform_deep_summarize_chunk(request, user, STORY_TOKENIZER, STORY_GENERATOR)

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