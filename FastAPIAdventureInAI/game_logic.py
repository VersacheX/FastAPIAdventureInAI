from ai_client_requests import ai_summarize_chunk, ai_prime_narrator, ai_generate_story

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
        from ai_settings import get_ai_settings
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

############################ LOGIC SETUP TO AI API CALLS ############################

def generate_story(context, user_input=None, include_initial=False, settings=None, username=None):
    """
    Generate story using AI server.
    Settings dict should contain AI configuration.
    """
    if settings is None:
        from ai_settings import get_ai_settings
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
        from ai_settings import get_ai_settings
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
        from ai_settings import get_ai_settings
        settings = get_ai_settings()
        max_tokens = settings.get('TOKENIZED_HISTORY_BLOCK_SIZE')
    
    summary = ai_summarize_chunk(chunk, max_tokens)
    return summary

############################# SETUP NEW/LOADED GAME CONTEXT ############################

def setup_load_game(loaded_game, token, user, WORLD_CACHE, RATING_CACHE):
    world = WORLD_CACHE.get(loaded_game.world_id, {})
    rating = RATING_CACHE.get(loaded_game.rating_id, {})
    context = {
        'player_world': world.get("name", ""),
        'setup': world.get("preface", ""),
        'world_tokens': world.get("world_tokens", ""),
        'game_rating': rating.get("name", ""),
        'story_splitter': f"# Continue {rating.get('ai_prompt', '')} after the player action.",
        'history': [h.entry for h in loaded_game.history],
        'tokenized_history': [th.model_dump() for th in loaded_game.tokenized_history or []],
        'token_count': 0,
        'player_name': loaded_game.player_name,
        'player_gender': loaded_game.player_gender,
        'game_id': loaded_game.id
    }
    user_id = user.id
    world_id = loaded_game.world_id
    rating_id = loaded_game.rating_id

    return context, user_id, world_id, rating_id

def setup_new_game(player_world, player_name, player_gender, game_rating, token, user, WORLD_CACHE, RATING_CACHE):
    gender_value = "Male" if player_gender.lower() == "m" else "Female"
    world_id = next((wid for wid, w in WORLD_CACHE.items() if w["name"] == player_world["name"]), None)
    rating_id = list(RATING_CACHE.keys())[game_rating]
    context = {
        'player_world': player_world["name"],
        'setup': player_world["preface"],
        'world_tokens': player_world["world_tokens"],
        'game_rating': RATING_CACHE[rating_id]["name"],
        'story_splitter': f"# Continue {RATING_CACHE[rating_id]['ai_prompt']} after the player action.",
        'history': [],
        'tokenized_history': [],
        'token_count': 0,
        'player_name': player_name,
        'player_gender': gender_value,
        'game_id': 0
    }
    user_id = user.id

    return context, user_id, world_id, rating_id