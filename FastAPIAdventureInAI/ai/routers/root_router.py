#import asyncio
#import uvicorn
import random
import re
from fastapi import APIRouter, Request, Depends#, HTTPException, status
#from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
#from fastapi.middleware.cors import CORSMiddleware
#from pydantic import BaseModel
#from typing import Optional, List, Dict
#import re
#import jwt
#from jwt.exceptions import InvalidTokenError

from starlette.concurrency import run_in_threadpool

# Import configuration from environment
from config import CORS_ORIGINS, SECRET_KEY, ALGORITHM

from ai.schemas_ai_server import *
#from ai.services.lookup_ai_service import describe_entity_ai
from ai.services.ai_api_service import perform_deep_summarize_chunk, perform_count_tokens, flatten_json_prompt, build_story_messages
from ai.services.ai_modeler_service import load_story_generater_to_app_state, get_model
from shared.helpers.ai_settings import get_ai_settings, get_user_ai_settings
from shared.services.auth_service import verify_token, get_current_claims
from shared.services.orm_service import get_db


router = APIRouter(tags=["root"])


# Grammatical glue words that disappear when the model drops into
# telegraphic / run-on "caveman" mode. Fluent English keeps a healthy
# ratio of these relative to total words.
_FUNCTION_WORDS = {
    "the", "a", "an", "her", "his", "their", "its", "and", "but", "or",
    "of", "to", "in", "into", "on", "at", "with", "as", "for", "from",
    "that", "this", "was", "were", "is", "are", "had", "has", "she",
    "he", "they", "him", "them",
}


def is_broken_prose(text: str) -> bool:
    """Heuristic detector for telegraphic / run-on "caveman English".

    Two independent symptoms of the failure mode we keep seeing:
      1. Very long sentences with no terminal punctuation (run-ons).
      2. A collapsed ratio of grammatical glue words (dropped articles /
         pronouns / conjunctions).

    Returning True means the text should be rejected and regenerated so it
    never enters story history (where it contaminates later generations).
    """
    words = re.findall(r"[A-Za-z']+", text)
    if len(words) < 25:
        # Too short to judge reliably; let it through.
        return False

    # 1) Run-on check: words per sentence-ending punctuation mark.
    sentence_ends = len(re.findall(r"[.!?]", text))
    words_per_sentence = len(words) / max(sentence_ends, 1)
    if words_per_sentence > 60:
        return True

    # 2) Function-word ratio check.
    function_count = sum(1 for w in words if w.lower() in _FUNCTION_WORDS)
    function_ratio = function_count / len(words)
    if function_ratio < 0.18:
        return True

    return False


def _normalize(text: str) -> str:
    """Lowercase + collapse whitespace/punctuation for fuzzy comparison."""
    return re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()


def is_echo_of_history(text: str, recent_entries) -> bool:
    """Detect when the model parroted a recent entry instead of continuing.

    Compares the generated text against each recent story entry using a word
    n-gram (shingle) overlap. A high overlap means the model reproduced prior
    narration almost verbatim, so it should be rejected and regenerated.
    """
    gen = _normalize(text)
    gen_words = gen.split()
    if len(gen_words) < 12:
        return False

    # Build a set of 6-word shingles from the generated text.
    n = 6
    gen_shingles = {
        " ".join(gen_words[i:i + n]) for i in range(len(gen_words) - n + 1)
    }
    if not gen_shingles:
        return False

    for entry in recent_entries or []:
        entry_words = _normalize(entry).split()
        if len(entry_words) < n:
            continue
        entry_shingles = {
            " ".join(entry_words[i:i + n]) for i in range(len(entry_words) - n + 1)
        }
        if not entry_shingles:
            continue
        overlap = len(gen_shingles & entry_shingles) / len(gen_shingles)
        # >35% of the generated 6-grams already appeared in a single prior
        # entry => it's regurgitating, not continuing.
        if overlap > 0.35:
            return True

    return False


@router.post("/prime_narrator/")
async def prime_narrator(db=Depends(get_db), user=Depends(get_current_claims), engine = Depends(get_model)):
    #settings = get_user_ai_settings(user.id)
    # You can use settings here if needed
    _ = await run_in_threadpool(
        lambda: engine.generate("Prime the narrator.", max_new_tokens=1)
    )
    return {"status": "primed"}

@router.post("/generate_from_game/")
async def generate_from_game(request: GenerateFromGameRequest, user=Depends(get_current_claims), engine = Depends(get_model)):
    # """
    # Accepts game data directly and builds structured JSON before generating story.
    # This endpoint is designed for React clients to call directly.
    # """
    settings = get_user_ai_settings(user.id)
    # Set random seed for reproducibility
    random.seed(random.randint(0, 2**32 - 1))

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

    # Build a ChatML message list (system/user/assistant/user) so the recent
    # story is framed as the narrator's PRIOR output. This stops the model from
    # copying the most recent entries verbatim and makes it continue instead.
    messages = build_story_messages(
        structured_json,
        settings,
        engine,
        system_prompt=settings.get("STORYTELLER_PROMPT"),
    )

    # Print the full prompt to console
    # print("\n" + "="*80)
    # print("PROMPT BEING SENT TO AI:")
    # print("="*80)
    # print(messages)
    # print("="*80 + "\n")

    # Cap retries low: StoryEngine serialises ALL model access, so a single
    # request looping many full generations would monopolise the GPU and block
    # every other inference request. A false-positive prose/echo rejection must
    # not stall the server, so we accept whatever we have after a few attempts.
    max_retries = 4
    text = ""
    for attempt in range(1, max_retries + 1):
        text = await run_in_threadpool(
            lambda: engine.generate_messages(
                messages,
                max_new_tokens=settings.get("RESERVED_FOR_GENERATION", 150),
                temperature=0.8,
                top_p=0.95,
                repetition_penalty=1.1,
                frequency_penalty=0.0,
                presence_penalty=0.0,
            )
        )

        # Remove lines starting with any stop token
        for stop_token in settings.get("STOP_TOKENS", ""):
            if text.strip().startswith(stop_token):
                text = text.strip()[len(stop_token):].lstrip()

        # Remove entire lines containing chapter markers (e.g., "Chapter 1.2.3:" or "1.2.5:" or "1.2:")
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
            # Reject bad output so it never gets saved to history and
            # contaminates later generations. On the final attempt, accept
            # whatever we have to guarantee the endpoint returns something.
            if attempt < max_retries:
                if is_broken_prose(text):
                    print(f"[Prose Gate] Rejected broken output on attempt {attempt}, retrying...")
                    continue
                if is_echo_of_history(text, structured_json.get("RecentStory", [])):
                    print(f"[Prose Gate] Rejected verbatim echo of history on attempt {attempt}, retrying...")
                    continue
            break

        print(f"OUTPUT:{text}")

    return {"story": text.strip()}

@router.post("/summarize_chunk/")
async def summarize_chunk(request: SummarizeChunkRequest, user=Depends(get_current_claims), engine = Depends(get_model)):
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
    
    header_tokens = engine.count_tokens(header)
    footer_tokens = engine.count_tokens(footer)
    reserved_tokens = max_tokens  # Reserve space for the summary output

    # Calculate available budget for chunk content
    available_tokens = settings.get("SAFE_PROMPT_LIMIT", 3900) - header_tokens - footer_tokens - reserved_tokens

    # Add chunk entries until we run out of budget
    chunk_text_parts = []
    for entry in chunk:
        entry_text = entry.strip() + "\n"
        entry_tokens = engine.count_tokens(entry_text)

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
                    test_tokens = engine.count_tokens(test_text)
                    if test_tokens <= available_tokens:
                        truncated = test_text
                    else:
                        break
                if truncated:
                    chunk_text_parts.append(truncated + "...\n")
            break

    prompt = header + "".join(chunk_text_parts) + footer

    # Log the token count
    final_tokens = engine.count_tokens(prompt)
    # print(f"\n[Summarize Token Budget] Prompt: {final_tokens} tokens (limit: {settings.get('SAFE_PROMPT_LIMIT', 3900)})")
    # print(f"[Summarize Token Budget] Chunk entries included: {len(chunk_text_parts)}/{len(chunk)}")

    # print("\n" + "="*80)
    # print("SUMMARIZE_CHUNK - AI PROMPT:")
    # print("="*80)
    # print(prompt)
    # print("="*80 + "\n")

    # Single attempt - accept whatever concise summary the AI produces
    summary_text = await run_in_threadpool(
        lambda: engine.generate(
            prompt,
            max_new_tokens=max_tokens,
            temperature=0.2,
            top_p=0.90,
            repetition_penalty=1.1
        )
    )

    # Strip everything before the marker
    if settings.get("SUMMARY_SPLIT_MARKER", "<<<SPLIT_MARKER>>>") in summary_text:
        summary_text = summary_text.split(settings.get("SUMMARY_SPLIT_MARKER", "<<<SPLIT_MARKER>>>"))[-1]

    summary_text = summary_text.strip()

    print("\n" + "="*80)
    print("SUMMARIZE_CHUNK - AI RESPONSE (after split marker removal):")
    print("="*80)
    print(summary_text)
    print(f"Token count: {engine.count_tokens(summary_text)}")
    print("="*80 + "\n")

    return {"summary": summary_text}


@router.post("/deep_summarize_chunk/")
async def deep_summarize_chunk(request: DeepSummarizeChunkRequest, user=Depends(get_current_claims), engine = Depends(get_model)):
    return await perform_deep_summarize_chunk(request, user, engine)
