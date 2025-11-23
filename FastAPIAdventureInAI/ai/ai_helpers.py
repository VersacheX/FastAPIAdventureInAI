"""
AI helper functions for story generation and history management.
"""
from ai.ai_client_requests import ai_summarize_chunk, ai_prime_narrator, ai_generate_story
from ai.ai_settings import get_ai_settings
from ai.schemas_ai_server import *
from business.models import User
from starlette.concurrency import run_in_threadpool

def get_user_ai_settings(user_id: int):
    return get_ai_settings(None, None, user_id)

def get_recent_memories(memory_log, limit=None):
    """
    Get the most recent memories from a log.
    Limit should be passed from loaded settings.
    """
    if limit is None:
        return memory_log
    return memory_log[-limit:]


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


def generate_story(context, user_input=None, include_initial=False, settings=None, username=None):
    """
    Generate story using AI server.
    Settings dict should contain AI configuration.
    """
    if settings is None:
        settings = get_ai_settings()
        
    if include_initial:
        ai_prime_narrator(username=username)
        context["history"].append(context['setup'])
        print(context['setup'] + "\n")
    
    # Use the AI server for story generation
    story = ai_generate_story(
        build_structured_json(context, user_input or "", settings), 
        user_input or "", 
        include_initial,
        username=username
    )
    if story.strip():
        context["history"].append(story.strip())
    return story.strip()


def tokenize_history(context, settings=None):
    """
    Tokenize history when enough entries have accumulated.
    Settings dict should contain: MEMORY_BACKLOG_LIMIT, RECENT_MEMORY_LIMIT, 
                                  TOKENIZE_HISTORY_CHUNK_SIZE, TOKENIZED_HISTORY_BLOCK_SIZE
    """
    if settings is None:
        settings = get_ai_settings()
    
    history = context["history"]
    tokenized_history = context["tokenized_history"]

    # Determine where the last tokenized block ended
    last_block_end = tokenized_history[-1]["end_index"] if tokenized_history else 0
    entries_since_last_block = len(history) - last_block_end

    # Only tokenize if enough new history has accumulated
    if entries_since_last_block >= settings.get('MEMORY_BACKLOG_LIMIT'):
        # Start at RECENT_MEMORY_LIMIT from the end, or last_block_end
        start_index = max(
            last_block_end, 
            len(history) - settings.get('RECENT_MEMORY_LIMIT') - settings.get('TOKENIZE_HISTORY_CHUNK_SIZE')
        )
        end_index = min(start_index + settings.get('TOKENIZE_HISTORY_CHUNK_SIZE'), len(history))
        chunk = history[start_index:end_index]

        # Summarize the chunk using the AI model
        summary = summarize_chunk(chunk, max_tokens=settings.get('TOKENIZED_HISTORY_BLOCK_SIZE'))
        
        block = {
            "start_index": start_index,
            "end_index": end_index,
            "summary": summary
        }
        tokenized_history.append(block)
        context["tokenized_history"] = tokenized_history
        return True 

    context["tokenized_history"] = tokenized_history
    return False 


def summarize_chunk(chunk, max_tokens=None):
    """
    Summarize a chunk of history entries.
    max_tokens should be passed from loaded settings.
    """
    if max_tokens is None:
        settings = get_ai_settings()
        max_tokens = settings.get('TOKENIZED_HISTORY_BLOCK_SIZE')
    
    summary = ai_summarize_chunk(chunk, max_tokens)
    return summary

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