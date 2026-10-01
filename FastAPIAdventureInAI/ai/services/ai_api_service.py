"""
AI helper functions for story generation and history management.
"""
import re
from fastapi import Request
#from ai.ai_client_requests import ai_summarize_chunk, ai_prime_narrator, ai_generate_story
from ai.schemas_ai_server import *
from business.models import User
from starlette.concurrency import run_in_threadpool
from config import CORS_ORIGINS, SECRET_KEY, ALGORITHM
from shared.helpers.memory_helper import get_recent_memories
from shared.helpers.ai_settings import get_ai_settings, get_user_ai_settings


def _clean_generated_text(text: str, stop_tokens=None, story_splitter: str = None) -> str:
    """Strip model artifacts (stop tokens, chapter markers, splitter, prompt
    echoes) from raw generation output. Pure string work -- no model call -- so
    it can be applied to any generation (story, summary, repair) identically.
    """
    # Remove lines starting with any stop token
    for stop_token in stop_tokens or "":
        if text.strip().startswith(stop_token):
            text = text.strip()[len(stop_token):].lstrip()

    # Remove chapter markers (e.g. "Chapter 1.2.3:" or "1.2:")
    text = re.sub(r'^\s*Chapter\s+\d+\.\d+(\.\d+)?:\s*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'^\s*\d+\.\d+(\.\d+)?:\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*Chapter\s+\d+\.\d+(\.\d+)?:\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\s*\d+\.\d+(\.\d+)?:\s*', '', text)

    # Remove story splitter if it appears in output
    if story_splitter and story_splitter in text:
        text = text.split(story_splitter)[-1].strip()

    # Remove common prompt artifacts
    text = re.sub(
        r'#\s*(No player action|Current Player Action|Continue|Recent Story).*$',
        '', text, flags=re.MULTILINE | re.IGNORECASE,
    )
    return text.strip()

def flatten_json_prompt(json_data, settings, STORY_ENGINE):
    """Build optimized prompt from structured game data with token budget enforcement.

    DEPRECATED for the main story route: this flattens everything into a single
    user string, which makes the model unable to tell "already-written
    narration" from "what to continue" and causes verbatim echoing of the most
    recent entries. Prefer build_story_messages() which uses proper chat roles.
    Kept for backwards compatibility / other callers.
    """
    context_block, recent_story_block, action_block, _stats = _build_prompt_blocks(
        json_data, settings, STORY_ENGINE
    )
    prompt = context_block
    if recent_story_block:
        prompt += f"# Recent Story:\n{recent_story_block}\n\n"
    prompt += action_block
    return prompt


def build_story_messages(json_data, settings, STORY_ENGINE, system_prompt=None):
    """Build a ChatML message list for story continuation.

    Using distinct roles is what stops the model from copying the most recent
    entries verbatim:
      - system    : narrator rules
      - user      : universe / player / rating + deep & compressed past events
      - assistant : the recent story (narration the narrator already produced)
      - user      : the player's action + an explicit "continue, don't repeat"

    Because the recent story is framed as the assistant's PRIOR output, the model
    treats the final user turn as a request for the NEXT beat rather than a
    pattern to reproduce.
    """
    context_block, recent_story_block, action_block, stats = _build_prompt_blocks(
        json_data, settings, STORY_ENGINE, system_prompt=system_prompt
    )

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # Setup / context as the first user turn.
    messages.append({"role": "user", "content": context_block.strip()})

    # Recent story becomes the assistant's prior narration.
    if recent_story_block:
        messages.append({"role": "assistant", "content": recent_story_block.strip()})

    # Final user turn: the action plus an explicit continuation directive.
    messages.append({"role": "user", "content": action_block.strip()})

    final_tokens = sum(STORY_ENGINE.count_tokens(m["content"]) for m in messages)
    print(f"[Token Budget] Final prompt: {final_tokens} tokens (limit: {settings.get('SAFE_PROMPT_LIMIT', 3901)})")
    print(f"[Token Budget] MEMORIES: {stats['block_tokens']} ACTIONS: {stats['action_tokens']} BASE: {stats['base_tokens']} RECENT HISTORY: {stats['entry_tokens']} SYSTEM: {stats['system_tokens']} TEMPLATE: {stats['template_overhead']}")

    return messages


def _build_prompt_blocks(json_data, settings, STORY_ENGINE, system_prompt=None):
    """Shared budget-aware builder returning the prompt in separate blocks.

    Returns (context_block, recent_story_block, action_block, stats) where
    context_block holds universe/player/rating + ancient & compressed history,
    recent_story_block holds the uncompressed recent entries (no header), and
    action_block holds the player's action plus the continuation directive.

    The budget reserves tokens for the system prompt (narrator directives) and
    an estimate of the chat template's per-message overhead so the final rendered
    prompt does not overflow the context window.
    """
    recent_story = json_data.get("RecentStory", [])
    tokenized_history = json_data.get("TokenizedHistory", [])
    deep_memory = json_data.get("DeepMemory")  # Ultra-compressed ancient history

    # Core context. NOTE: Narrator Directives are sent as the chat system
    # message, so they are intentionally NOT duplicated here.
    context_block = (
        f"# Universe: {json_data['UniverseName']}\n"
        f"{json_data['UniverseTokens']}\n\n"
        f"# Player: {json_data['PlayerInfo']['Name']} ({json_data['PlayerInfo']['Gender']})\n"
        f"# Rating: {json_data['GameSettings']['Rating']}\n\n"
    )

    base_tokens = STORY_ENGINE.count_tokens(context_block)
    tokens_used = base_tokens

    # Reserve budget for the system prompt plus chat-template framing overhead.
    # Each message rendered by the chat template adds role/delimiter tokens
    # (roughly 4 tokens per message for ChatML). We account for up to 4 messages
    # (system/user/assistant/user) so the final rendered prompt stays within the
    # safe limit.
    system_tokens = STORY_ENGINE.count_tokens(system_prompt) if system_prompt else 0
    template_overhead = 4 * 4
    tokens_used += system_tokens + template_overhead

    # Build the action / continuation block.
    current_action = json_data['CurrentAction'].strip()
    if current_action:
        action_mode = json_data.get("ActionMode", "ACTION")
        if action_mode == "SPEECH":
            action_text = f"# Player Says: \"{current_action}\"\n\n"
        elif action_mode == "NARRATE":
            action_text = f"# Player Narrative: {current_action}\n\n"
        else:
            action_text = f"# Player Action: {current_action}\n\n"
    else:
        action_text = "# No Player Action.\n\n"

    # Explicit continuation directive so the model advances instead of echoing.
    action_text += (
        "# Instruction: Continue the story from this exact moment. Write what "
        "happens NEXT as new narration. Do NOT repeat, rephrase, or summarize "
        "any previous entry.\n"
    )
    action_tokens = STORY_ENGINE.count_tokens(action_text)
    tokens_used += action_tokens

    available_tokens = settings.get("SAFE_PROMPT_LIMIT", 3900) - tokens_used

    # Deep memory (ultra-compressed ancient history).
    if deep_memory and available_tokens > 0:
        deep_section = f"# Ancient History (Major Events):\n{deep_memory.strip()}\n\n"
        deep_tokens = STORY_ENGINE.count_tokens(deep_section)
        if deep_tokens <= available_tokens:
            context_block += deep_section
            tokens_used += deep_tokens
            available_tokens -= deep_tokens

    total_block_tokens = 0
    # Compressed history (most recent summaries first).
    if tokenized_history and available_tokens > 0:
        recent_blocks = list(reversed(tokenized_history[-settings.get("MAX_TOKENIZED_HISTORY_BLOCK", 4):]))
        blocks_to_include = []
        for block in recent_blocks:
            summary = block.get("summary", "").strip()
            if summary:
                block_text = f"{summary}\n\n"
                block_tokens = STORY_ENGINE.count_tokens(block_text)
                if block_tokens <= available_tokens:
                    total_block_tokens += block_tokens
                    blocks_to_include.insert(0, block_text)
                    available_tokens -= block_tokens
                else:
                    break
        if blocks_to_include:
            context_block += "# Past Events:\n"
            for block_text in blocks_to_include:
                context_block += block_text

    total_entry_tokens = 0
    recent_story_block = ""
    # Recent chronological story (budget constrained, most recent first).
    if recent_story and available_tokens > 0:
        recent_entries = list(reversed(recent_story))
        entries_to_include = []
        for entry in recent_entries:
            entry_text = f"{entry.strip()}\n\n"
            entry_tokens = STORY_ENGINE.count_tokens(entry_text)
            if entry_tokens <= available_tokens:
                total_entry_tokens += entry_tokens
                entries_to_include.insert(0, entry_text)
                available_tokens -= entry_tokens
            else:
                break
        recent_story_block = "".join(entries_to_include).strip()

    stats = {
        "base_tokens": base_tokens,
        "system_tokens": system_tokens,
        "template_overhead": template_overhead,
        "action_tokens": action_tokens,
        "block_tokens": total_block_tokens,
        "entry_tokens": total_entry_tokens,
    }
    return context_block, recent_story_block, action_text, stats

# THIS CAN STAY REMANE TO build_structured_json_from_context  ... also we should rename this file as ai_service
def build_structured_json(context, user_input, settings=None):
    """
    Build structured JSON for AI generation.
    Settings dict should contain: STORYTELLER_PROMPT, MAX_TOKENIZED_HISTORY_BLOCK, RECENT_MEMORY_LIMIT
    """
    if settings is None:
        # Fallback to loading from ai_settings if not provided
        settings = get_ai_settings()
    
    if not user_input.strip() == '':
        context["history"].append(user_input)
    else:
        user_input = ''

    history = get_recent_memories(context["history"], settings.get('RECENT_MEMORY_LIMIT'))
    if len(history) > 1:
        history = history[:-1]
    
    tokenized_history = get_recent_memories(
        context["tokenized_history"], 
        settings.get('MAX_TOKENIZED_HISTORY_BLOCK')
    )
    
    structured = {
        "NarratorDirectives": settings.get('STORYTELLER_PROMPT'),
        "UniverseName": context["player_world"],
        "UniverseTokens": context["world_tokens"],
        "StoryPreface": context["setup"],
        "GameSettings": {
            "Rating": context["game_rating"],
            "StorySplitter": context["story_splitter"]
        },
        "PlayerInfo": {
            "Name": context["player_name"],
            "Gender": context["player_gender"]
        },
        "TokenizedHistory": tokenized_history,
        "RecentStory": history,
        "FullHistory": context["history"],
        "CurrentAction": user_input
    }
    return structured 

# THIS CAN STAY REMANE TO generate_story
# def generate_story(context, user_input=None, include_initial=False, settings=None, username=None):
#     """
#     Generate story using AI server.
#     Settings dict should contain AI configuration.
#     """
#     if settings is None:
#         settings = get_ai_settings()
        
#     if include_initial:
#         ai_prime_narrator(username=username)
#         context["history"].append(context['setup'])
#         print(context['setup'] + "\n")
    
#     # Use the AI server for story generation
#     story = ai_generate_story(
#         build_structured_json(context, user_input or "", settings), 
#         user_input or "", 
#         include_initial,
#         username=username
#     )
#     if story.strip():
#         context["history"].append(story.strip())
#     return story.strip()

# DEFINITELY STAY rename to tokenize_story_history
# def tokenize_history(context, settings=None):
#     """
#     Tokenize history when enough entries have accumulated.
#     Settings dict should contain: MEMORY_BACKLOG_LIMIT, RECENT_MEMORY_LIMIT, 
#                                   TOKENIZE_HISTORY_CHUNK_SIZE, TOKENIZED_HISTORY_BLOCK_SIZE
#     """
#     if settings is None:
#         settings = get_ai_settings()
    
#     history = context["history"]
#     tokenized_history = context["tokenized_history"]

#     # Determine where the last tokenized block ended
#     last_block_end = tokenized_history[-1]["end_index"] if tokenized_history else 0
#     entries_since_last_block = len(history) - last_block_end

#     # Only tokenize if enough new history has accumulated
#     if entries_since_last_block >= settings.get('MEMORY_BACKLOG_LIMIT'):
#         # Start at RECENT_MEMORY_LIMIT from the end, or last_block_end
#         start_index = max(
#             last_block_end, 
#             len(history) - settings.get('RECENT_MEMORY_LIMIT') - settings.get('TOKENIZE_HISTORY_CHUNK_SIZE')
#         )
#         end_index = min(start_index + settings.get('TOKENIZE_HISTORY_CHUNK_SIZE'), len(history))
#         chunk = history[start_index:end_index]

#         # Summarize the chunk using the AI model
#         summary = summarize_chunk(chunk, max_tokens=settings.get('TOKENIZED_HISTORY_BLOCK_SIZE'))
        
#         block = {
#             "start_index": start_index,
#             "end_index": end_index,
#             "summary": summary
#         }
#         tokenized_history.append(block)
#         context["tokenized_history"] = tokenized_history
#         return True 

#     context["tokenized_history"] = tokenized_history
#     return False 

# THIS CAN STAY rename to summarize_history_chunk
# def summarize_chunk(chunk, max_tokens=None):
#     """
#     Summarize a chunk of history entries.
#     max_tokens should be passed from loaded settings.
#     """
#     if max_tokens is None:
#         settings = get_ai_settings()
#         max_tokens = settings.get('TOKENIZED_HISTORY_BLOCK_SIZE')
    
#     summary = ai_summarize_chunk(chunk, max_tokens)
#     return summary

# THIS CAN STAY
async def perform_count_tokens(request: Request, STORY_ENGINE):
    """Count tokens in a single text string."""
    body = await request.json()
    text = body.get("text", "")

    # count_tokens acquires the engine's synchronous model lock. Run it in a
    # worker thread so a concurrent generation holding that lock cannot block
    # the async event loop for the full generation duration.
    token_count = await run_in_threadpool(STORY_ENGINE.count_tokens, text)
    return {"token_count": token_count}

# THIS CAN STAY
async def perform_deep_summarize_chunk(request: DeepSummarizeChunkRequest, user: User, STORY_ENGINE):
    chunk = request.chunk
    max_tokens = request.max_tokens
    previous_summary = request.previous_summary

    settings = get_user_ai_settings(user.id)
    SAFE_PROMPT_LIMIT = settings.get("SAFE_PROMPT_LIMIT", 3900)
    SUMMARY_SPLIT_MARKER = settings.get("SUMMARY_SPLIT_MARKER", "<<<SPLIT_MARKER>>>")

    # Deep (ancient) memory compression. Like the chunk summarizer, this must use
    # proper chat roles: the directive goes in the SYSTEM turn and the chapter
    # summaries go in the USER turn. Previously the raw chunk was sent with no
    # instructions at all (just a trailing marker), so the instruct model simply
    # echoed the text back instead of compressing it.
    system_prompt = (
        "You are a long-term memory compressor. You are given one or more "
        "chapter summaries describing ancient story history. Merge them into a "
        "single, ultra-compressed record of ONLY the most important, lasting "
        "facts: major plot outcomes, permanent world/state changes, key "
        "character arcs and relationships, and unresolved threads.\n"
        "Rules:\n"
        "  - Preserve continuity across ALL provided history.\n"
        "  - Be extremely terse; drop anything minor or transient.\n"
        "  - Do NOT continue the story and do NOT copy sentences verbatim.\n"
        "  - Output ONLY the merged summary as plain text, no formatting.\n"
    )

    # Include the existing deep-memory summary so a second compression does not
    # discard previously retained ancient history -- it gets merged forward.
    user_parts = []
    if previous_summary:
        user_parts.append(
            "# Existing ancient-history summary (KEEP these facts, merge forward):\n"
            f"{previous_summary.strip()}\n"
        )
    user_parts.append(
        "# New chapter summaries to merge in:\n"
        f"{chunk.strip()}"
    )
    user_content = "\n".join(user_parts)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    final_tokens = sum(STORY_ENGINE.count_tokens(m["content"]) for m in messages)
    print(f"\n[Deep Summarize Token Budget] Prompt: {final_tokens} tokens (limit: {SAFE_PROMPT_LIMIT})")

    # Single attempt - accept whatever concise summary the AI produces
    summary_text = await run_in_threadpool(
        lambda: STORY_ENGINE.generate_messages(
            messages,
            max_new_tokens=max_tokens,
            temperature=0.5,
            top_p=0.90,
            repetition_penalty=1.1,
        )
    )

    # Legacy split marker: strip it if present
    if SUMMARY_SPLIT_MARKER in summary_text:
        summary_text = summary_text.split(SUMMARY_SPLIT_MARKER)[-1]

    # Shared artifact cleanup: stop tokens, chapter markers, prompt echoes.
    summary_text = _clean_generated_text(summary_text, settings.get("STOP_TOKENS", ""))
    summary_text = summary_text.strip()

    print("\n" + "="*80)
    print("SUMMARIZE_CHUNK - AI RESPONSE (after split marker removal):")
    print("="*80)
    print(summary_text)
    print(f"Token count: {STORY_ENGINE.count_tokens(summary_text)}")
    print("="*80 + "\n")

    return {"summary": summary_text}
