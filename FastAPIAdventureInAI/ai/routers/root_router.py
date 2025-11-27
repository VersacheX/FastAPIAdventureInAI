#import asyncio
#import uvicorn
import random
from typing import Tuple
from fastapi import APIRouter, Request, Depends#, HTTPException, status
#from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
#from fastapi.middleware.cors import CORSMiddleware
#from pydantic import BaseModel
#from typing import Optional, List, Dict
#import re
#import jwt
#from jwt.exceptions import InvalidTokenError

from starlette.concurrency import run_in_threadpool

# Import your AI model setup and logic here
#from gptqmodel.models import GPTQModel
from transformers import set_seed#, AutoTokenizer

# Import configuration from environment
from config import CORS_ORIGINS, SECRET_KEY, ALGORITHM

from ai.schemas_ai_server import *
#from ai.services.lookup_ai_service import describe_entity_ai
from ai.services.ai_api_service import perform_deep_summarize_chunk, perform_count_tokens, flatten_json_prompt
from ai.services.ai_modeler_service import load_story_generater_to_app_state, get_model
from shared.helpers.ai_settings import get_ai_settings, get_user_ai_settings
from shared.services.auth_service import verify_token, get_current_user
from shared.services.orm_service import get_db


router = APIRouter(tags=["root"])

@router.post("/prime_narrator/")
async def prime_narrator(db=Depends(get_db), user=Depends(get_current_user), model_and_tokenizer: Tuple = Depends(get_model)):
    generator, tokenizer = model_and_tokenizer
    #settings = get_user_ai_settings(user.id)
    # You can use settings here if needed
    inputs = await run_in_threadpool(lambda: tokenizer("Prime the narrator.", return_tensors="pt").to("cuda"))
    _ = await run_in_threadpool(
        lambda: generator.generate(
            **inputs,
            max_new_tokens=1,
            num_return_sequences=1
        )
    )
    return {"status": "primed"}

@router.post("/generate_from_game/")
async def generate_from_game(request: GenerateFromGameRequest, user=Depends(get_current_user), model_and_tokenizer: Tuple = Depends(get_model)):
    # """
    # Accepts game data directly and builds structured JSON before generating story.
    # This endpoint is designed for React clients to call directly.
    # """
    generator, tokenizer = model_and_tokenizer
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
    prompt = flatten_json_prompt(structured_json, settings, tokenizer)
    
    # Print the full prompt to console
    # print("\n" + "="*80)
    # print("PROMPT BEING SENT TO AI:")
    # print("="*80)
    # print(prompt)
    # print("="*80 + "\n")

    inputs = await run_in_threadpool(lambda: tokenizer(prompt, return_tensors="pt").to("cuda"))
    prompt_token_count = inputs.input_ids.shape[-1]
    
    max_retries = 15
    text = ""
    for attempt in range(1, max_retries + 1):
        output = await run_in_threadpool(
            lambda: generator.generate(
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
        text = tokenizer.decode(generated_tokens, skip_special_tokens=True)

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

@router.post("/summarize_chunk/")
async def summarize_chunk(request: SummarizeChunkRequest, user=Depends(get_current_user), model_and_tokenizer: Tuple = Depends(get_model)):
    generator, tokenizer = model_and_tokenizer
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
        "Do not use any symbols or formatting-just plain text.\n"
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
    
    header_tokens = len(tokenizer.encode(header))
    footer_tokens = len(tokenizer.encode(footer))
    reserved_tokens = max_tokens  # Reserve space for the summary output
    
    # Calculate available budget for chunk content
    available_tokens = settings.get("SAFE_PROMPT_LIMIT", 3900) - header_tokens - footer_tokens - reserved_tokens
    
    # Add chunk entries until we run out of budget
    chunk_text_parts = []
    for entry in chunk:
        entry_text = entry.strip() + "\n"
        entry_tokens = len(tokenizer.encode(entry_text))
        
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
                    test_tokens = len(tokenizer.encode(test_text))
                    if test_tokens <= available_tokens:
                        truncated = test_text
                    else:
                        break
                if truncated:
                    chunk_text_parts.append(truncated + "...\n")
            break
    
    prompt = header + "".join(chunk_text_parts) + footer
    
    # Log the token count
    final_tokens = len(tokenizer.encode(prompt))
    # print(f"\n[Summarize Token Budget] Prompt: {final_tokens} tokens (limit: {settings.get('SAFE_PROMPT_LIMIT', 3900)})")
    # print(f"[Summarize Token Budget] Chunk entries included: {len(chunk_text_parts)}/{len(chunk)}")
    
    # print("\n" + "="*80)
    # print("SUMMARIZE_CHUNK - AI PROMPT:")
    # print("="*80)
    # print(prompt)
    # print("="*80 + "\n")
    
    # Single attempt - accept whatever concise summary the AI produces
    inputs = await run_in_threadpool(lambda: tokenizer(prompt, return_tensors="pt").to("cuda"))
    summary_output = await run_in_threadpool(
        lambda: generator.generate(
            **inputs,
            max_new_tokens=max_tokens,
            num_return_sequences=1,
            temperature=0.2,
            top_p=0.90,
            repetition_penalty=1.1
        )
    )
    summary_text = tokenizer.decode(summary_output[0], skip_special_tokens=True)

    # Strip everything before the marker
    if settings.get("SUMMARY_SPLIT_MARKER", "<<<SPLIT_MARKER>>>") in summary_text:
        summary_text = summary_text.split(settings.get("SUMMARY_SPLIT_MARKER", "<<<SPLIT_MARKER>>>"))[-1]

    summary_text = summary_text.strip()
    
    print("\n" + "="*80)
    print("SUMMARIZE_CHUNK - AI RESPONSE (after split marker removal):")
    print("="*80)
    print(summary_text)
    print(f"Token count: {len(tokenizer.encode(summary_text, add_special_tokens=False))}")
    print("="*80 + "\n")

    return {"summary": summary_text}


@router.post("/deep_summarize_chunk/")
async def deep_summarize_chunk(request: DeepSummarizeChunkRequest, user=Depends(get_current_user), model_and_tokenizer: Tuple = Depends(get_model)):
    generator, tokenizer = model_and_tokenizer
    return await perform_deep_summarize_chunk(request, user, tokenizer, generator)
