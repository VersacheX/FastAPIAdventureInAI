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
from ai.services.ai_api_service import perform_deep_summarize_chunk, perform_count_tokens, flatten_json_prompt, build_story_messages, _clean_generated_text
from ai.services.ai_modeler_service import load_story_generater_to_app_state, get_model
from shared.helpers.ai_settings import get_ai_settings, get_user_ai_settings, get_user_ai_settings_async
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


# Editor directive used by the repair pass. Framing the model as a copy editor
# with an explicit "preserve events, fix only the language" instruction makes a
# single repair generation far more reliable at fixing broken/telegraphic prose
# than a blind reroll of the same request.
_REPAIR_SYSTEM_PROMPT = (
    "You are a line editor. Rewrite the passage below in fluent, natural English. "
    "Preserve the events, characters, tone, and meaning EXACTLY -- do not add, "
    "remove, or invent anything. Fix only grammar, dropped articles/pronouns, and "
    "run-on sentences. Return ONLY the rewritten narration with no commentary, "
    "labels, or quotation marks."
)


async def _repair_prose(engine, text: str, max_new_tokens: int) -> str:
    """Run a single repair generation that rewrites broken prose cleanly.

    This is a full model call (same ~per-token cost as a retry), but a targeted
    "rewrite this fluently" task succeeds in one shot far more often than hoping
    a fresh random generation comes out clean -- so the effort is not wasted.
    """
    return await run_in_threadpool(
        lambda: engine.generate(
            text,
            max_new_tokens=max_new_tokens,
            temperature=0.4,
            top_p=0.9,
            repetition_penalty=1.1,
            system_prompt=_REPAIR_SYSTEM_PROMPT,
        )
    )


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
    settings = await get_user_ai_settings_async(user.id)
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
    # build_story_messages() makes many engine.count_tokens() calls, each of
    # which acquires the model lock, so offload it to a worker thread to avoid
    # blocking the event loop while another request is generating.
    messages = await run_in_threadpool(
        build_story_messages,
        structured_json,
        settings,
        engine,
        settings.get("STORYTELLER_PROMPT"),
    )

    # Print the full prompt to console
    # print("\n" + "="*80)
    # print("PROMPT BEING SENT TO AI:")
    # print("="*80)
    # print(messages)
    # print("="*80 + "\n")

    # Hybrid quality gate (bounded to 2 model calls total). At ~5 tok/s every
    # generation is expensive, so instead of blindly rerolling we spend the
    # second call intelligently based on WHAT was wrong:
    #   - broken prose  -> REPAIR pass: feed the text back to be rewritten
    #                      cleanly (targeted, high one-shot success rate).
    #   - echo of past  -> fresh RETRY: rewording an echo doesn't help, so a new
    #                      generation is the right fix.
    #   - clean         -> accept immediately (one call, ~35s).
    # The first usable output is always kept as a fallback so no generation is
    # ever wasted.
    max_new_tokens = settings.get("RESERVED_FOR_GENERATION", 150)
    stop_tokens = settings.get("STOP_TOKENS", "")
    recent_story = structured_json.get("RecentStory", [])

    def _primary_generation():
        raw = engine.generate_messages(
            messages,
            max_new_tokens=max_new_tokens,
            temperature=0.8,
            top_p=0.95,
            repetition_penalty=1.1,
            frequency_penalty=0.0,
            presence_penalty=0.0,
        )
        return _clean_generated_text(raw, stop_tokens, request.story_splitter)

    text = await run_in_threadpool(_primary_generation)
    fallback_text = text  # best-so-far; never return empty if later steps fail

    if not text:
        # Empty completion: spend the available second call on a fresh attempt
        # rather than returning an empty story.
        print("[Prose Gate] Empty completion -> running one fresh retry...")
        text = await run_in_threadpool(_primary_generation)
        fallback_text = text
    elif is_broken_prose(text):
        # Repair the broken prose in a single targeted pass.
        print("[Prose Gate] Broken prose detected -> running repair pass...")
        repaired = await _repair_prose(engine, text, max_new_tokens)
        repaired = _clean_generated_text(repaired, stop_tokens, request.story_splitter)
        # Accept the repair only if it passes BOTH gates: a passage that was
        # broken may also be an echo, so re-validate against history too.
        if repaired and not is_broken_prose(repaired) and not is_echo_of_history(repaired, recent_story):
            text = repaired
        else:
            print("[Prose Gate] Repair pass did not improve output; keeping original.")
            text = fallback_text
    elif is_echo_of_history(text, recent_story):
        # Echo can't be edited away -> one fresh retry instead.
        print("[Prose Gate] Verbatim echo detected -> running one fresh retry...")
        retry = await run_in_threadpool(
            lambda: engine.generate_messages(
                messages,
                max_new_tokens=max_new_tokens,
                temperature=0.9,
                top_p=0.95,
                repetition_penalty=1.15,
                frequency_penalty=0.0,
                presence_penalty=0.0,
            )
        )
        retry = _clean_generated_text(retry, stop_tokens, request.story_splitter)
        # Keep the retry only if it passes BOTH quality gates.
        if retry and not is_echo_of_history(retry, recent_story) and not is_broken_prose(retry):
            text = retry
        else:
            print("[Prose Gate] Retry still echoed/broken/empty; keeping original.")
            text = fallback_text

    # Guarantee a non-empty return.
    if not text.strip():
        text = fallback_text

    print(f"OUTPUT:{text}")

    return {"story": text.strip()}

@router.post("/summarize_chunk/")
async def summarize_chunk(request: SummarizeChunkRequest, user=Depends(get_current_claims), engine = Depends(get_model)):
    chunk = request.chunk
    max_tokens = request.max_tokens
    previous_summary = request.previous_summary

    settings = await get_user_ai_settings_async(user.id)

    # Summarization instructions go in the SYSTEM role. On an instruct model,
    # mixing the directive and the story into a single flat user turn makes the
    # model continue/echo the story instead of summarizing it (the old
    # "<<<SPLIT_MARKER>>>" hack was a workaround for exactly that). Using proper
    # roles -- rules as system, story as user -- makes it actually summarize.
    system_prompt = (
        "You are a summarization engine. Condense the story segment the user "
        "provides into the most efficient summary possible.\n"
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
        "Write in bullet points or a single direct sentence. No narrative, "
        "review, or analysis. Do NOT continue the story. Do NOT copy sentences "
        "verbatim from the segment. Output ONLY the summary itself.\n"
        "Do not use any symbols or formatting-just plain text.\n"
    )

    # Budget the story content so system prompt + content + generation fit.
    # All of the token counting below acquires the engine's model lock, so the
    # entire budget construction runs in a worker thread to avoid blocking the
    # event loop while another request is generating.
    safe_prompt_limit = settings.get("SAFE_PROMPT_LIMIT", 3900)

    def _build_messages():
        system_tokens = engine.count_tokens(system_prompt)
        # ~4 tokens per message of ChatML framing across system/user turns.
        template_overhead = 4 * 2
        available_tokens = safe_prompt_limit - system_tokens - template_overhead - max_tokens

        # Optionally give the model the running summary as context so it doesn't
        # repeat already-captured events.
        context_prefix = ""
        if previous_summary:
            context_prefix = (
                "# Summary so far (already captured, do NOT repeat):\n"
                f"{previous_summary.strip()}\n\n"
            )
            available_tokens -= engine.count_tokens(context_prefix)

        # Add chunk entries until we run out of budget.
        chunk_text_parts = []
        for entry in chunk:
            entry_text = entry.strip() + "\n"
            entry_tokens = engine.count_tokens(entry_text)

            if entry_tokens <= available_tokens:
                chunk_text_parts.append(entry_text)
                available_tokens -= entry_tokens
            else:
                # If we can't fit the whole entry, truncate it.
                if len(chunk_text_parts) == 0:
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

        user_content = (
            f"{context_prefix}"
            "# Story Segment to summarize:\n"
            f"{''.join(chunk_text_parts).strip()}"
        )

        built = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        built_tokens = sum(engine.count_tokens(m["content"]) for m in built)
        return built, built_tokens

    messages, final_tokens = await run_in_threadpool(_build_messages)
    print(f"[Summarize Token Budget] Prompt: {final_tokens} tokens (limit: {safe_prompt_limit})")

    # Single attempt - accept whatever concise summary the AI produces.
    summary_text = await run_in_threadpool(
        lambda: engine.generate_messages(
            messages,
            max_new_tokens=max_tokens,
            temperature=0.2,
            top_p=0.90,
            repetition_penalty=1.1,
        )
    )

    # Legacy split marker: strip it if an older prompt/model still emits it.
    marker = settings.get("SUMMARY_SPLIT_MARKER", "<<<SPLIT_MARKER>>>")
    if marker in summary_text:
        summary_text = summary_text.split(marker)[-1]

    # Shared artifact cleanup (stop tokens, chapter markers, prompt echoes).
    summary_text = _clean_generated_text(summary_text, settings.get("STOP_TOKENS", ""), None)
    summary_text = summary_text.strip()

    print("\n" + "="*80)
    print("SUMMARIZE_CHUNK - AI RESPONSE:")
    print("="*80)
    print(summary_text)
    print("="*80 + "\n")

    return {"summary": summary_text}


@router.post("/deep_summarize_chunk/")
async def deep_summarize_chunk(request: DeepSummarizeChunkRequest, user=Depends(get_current_claims), engine = Depends(get_model)):
    return await perform_deep_summarize_chunk(request, user, engine)
