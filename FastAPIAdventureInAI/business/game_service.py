"""
Game setup and management service.
"""


def setup_load_game(loaded_game, token, user, WORLD_CACHE, RATING_CACHE):
    """
    Set up game context from a loaded saved game.
    
    Args:
        loaded_game: SavedGameDTO with game data
        token: Auth token
        user: User object
        WORLD_CACHE: Dictionary of world data
        RATING_CACHE: Dictionary of rating data
        
    Returns:
        Tuple of (context, user_id, world_id, rating_id)
    """
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
    """
    Set up game context for a new game.
    
    Args:
        player_world: World dictionary
        player_name: Player's name
        player_gender: Player's gender (m/f)
        game_rating: Rating index
        token: Auth token
        user: User object
        WORLD_CACHE: Dictionary of world data
        RATING_CACHE: Dictionary of rating data
        
    Returns:
        Tuple of (context, user_id, world_id, rating_id)
    """
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
