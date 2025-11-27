"""
AI helper functions for story generation and history management.
"""
from fastapi import Request
#from ai.ai_client_requests import ai_summarize_chunk, ai_prime_narrator, ai_generate_story
from ai.schemas_ai_server import *
from business.models import User
from starlette.concurrency import run_in_threadpool
from config import CORS_ORIGINS, SECRET_KEY, ALGORITHM
from shared.helpers.memory_helper import get_recent_memories
from shared.helpers.ai_settings import get_ai_settings, get_user_ai_settings

    
def flatten_json_prompt(json_data, settings, STORY_TOKENIZER):
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
async def perform_count_tokens(request: Request, STORY_TOKENIZER):
    """Count tokens in a single text string."""
    import asyncio
    body = await request.json()
    text = body.get("text", "")
    
    tokens = STORY_TOKENIZER.encode(text)
    return {"token_count": len(tokens)}

# THIS CAN STAY
async def perform_deep_summarize_chunk(request: DeepSummarizeChunkRequest, user: User, STORY_TOKENIZER, STORY_GENERATOR):
    prompt = request.chunk
    max_tokens = request.max_tokens
    #previous_summary = request.previous_summary

    settings = get_user_ai_settings(user.id)
    SAFE_PROMPT_LIMIT = settings.get("SAFE_PROMPT_LIMIT", 3900)
    SUMMARY_SPLIT_MARKER = settings.get("SUMMARY_SPLIT_MARKER", "<<<SPLIT_MARKER>>>")

    prompt+=f"\n{SUMMARY_SPLIT_MARKER}"
    # Log the token count
    final_tokens = len(STORY_TOKENIZER.encode(prompt))
    print(f"\n[Summarize Token Budget] Prompt: {final_tokens} tokens (limit: {SAFE_PROMPT_LIMIT})")
    
    # Single attempt - accept whatever concise summary the AI produces
    inputs = await run_in_threadpool(lambda: STORY_TOKENIZER(prompt, return_tensors="pt").to("cuda"))
    summary_output = await run_in_threadpool(
        lambda: STORY_GENERATOR.generate(
            **inputs,
            max_new_tokens=max_tokens,
            num_return_sequences=1,
            temperature=0.5,
            top_p=0.90,
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