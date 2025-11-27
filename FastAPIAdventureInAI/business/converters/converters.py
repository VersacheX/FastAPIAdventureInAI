from datetime import datetime, timezone
from business.models import User, World, GameRating, SavedGame, StoryHistory, TokenizedHistory, AccountLevel, AIDirectiveSettings
from business.dtos import UserDTO, WorldDTO, GameRatingDTO, SavedGameDTO, HistoryDTO, TokenizedHistoryDTO, AccountLevelDTO, AIDirectiveSettingsDTO

def account_level_to_dto(account_level: AccountLevel) -> AccountLevelDTO:
    # Let Pydantic map all fields from the SQLAlchemy model via from_attributes
    return AccountLevelDTO.model_validate(account_level)

def user_to_dto(user: User) -> UserDTO:
    return UserDTO.model_validate(user)

def world_to_dto(world: World, calculate_tokens: bool = True) -> WorldDTO:
    # Count the number of saved games using this world
    game_count = len(world.saved_games) if hasattr(world, 'saved_games') else 0
    # Use stored token_count if available
    token_count = world.token_count
    return WorldDTO(
        id=world.id,
        user_id=world.user_id,
        name=world.name,
        preface=world.preface,
        world_tokens=world.world_tokens,
        created_at=world.created_at,
        updated_at=world.updated_at,
        game_count=game_count,
        token_count=token_count
    )

def game_rating_to_dto(rating: GameRating) -> GameRatingDTO:
    return GameRatingDTO.model_validate(rating)

def history_to_dto(history: StoryHistory) -> HistoryDTO:
    # Convert is_tokenized from integer (0/1) to boolean
    return HistoryDTO(
        id=history.id,
        saved_game_id=history.saved_game_id,
        entry_index=history.entry_index,
        text=history.text,
        token_count=history.token_count,
        is_tokenized=bool(history.is_tokenized)
    )

def tokenized_history_to_dto(th: TokenizedHistory) -> TokenizedHistoryDTO:
    return TokenizedHistoryDTO.model_validate(th)

def saved_game_to_dto(game: SavedGame, history_list, tokenized_history_list, db=None) -> SavedGameDTO:
    # Fetch world and rating names and details
    world_name = ""
    world_tokens = ""
    world_preface = ""
    rating_name = ""
    story_splitter = "###"
    try:
        if hasattr(game, "world") and game.world:
            world_name = game.world.name
            world_tokens = game.world.world_tokens
            world_preface = game.world.preface
        elif db:
            world = db.query(World).filter(World.id == game.world_id).first()
            if world:
                world_name = world.name
                world_tokens = world.world_tokens
                world_preface = world.preface
        if hasattr(game, "rating") and game.rating:
            rating_name = game.rating.name
            story_splitter = f"# Continue {game.rating.ai_prompt} after the player action."
        elif db:
            rating = db.query(GameRating).filter(GameRating.id == game.rating_id).first()
            if rating:
                rating_name = rating.name
                story_splitter = f"# Continue {rating.ai_prompt} after the player action."
    except Exception:
        world_name = ""
        world_tokens = ""
        world_preface = ""
        rating_name = ""
        story_splitter = "###"

    # Get game settings
    # Use default values since settings are game-specific and we don't have all context here
    # Need AIDirectiveSettings found from User.account_level_id to AccountLevel.game_settings_id
    user = db.query(User).filter(User.id == game.user_id).first()
    account_level = db.query(AccountLevel).filter(AccountLevel.id == user.account_level_id).first() if user else None
    ai_settings = db.query(AIDirectiveSettings).filter(AIDirectiveSettings.id == account_level.game_settings_id).first() if account_level else None
    max_tokenized_history_block = ai_settings.max_tokenized_history_block if ai_settings and ai_settings.max_tokenized_history_block is not None else 4
    tokenize_threshold = ai_settings.tokenize_threshold if ai_settings and ai_settings.tokenize_threshold is not None else 800
    tokenized_history_block_size = ai_settings.tokenized_history_block_size if ai_settings and ai_settings.tokenized_history_block_size is not None else 200
    
    return SavedGameDTO(
        id=game.id,
        user_id=game.user_id,
        world_id=game.world_id,
        rating_id=game.rating_id,
        player_name=game.player_name,
        player_gender=game.player_gender,
        history_count=len(history_list),
        world_name=world_name,
        world_tokens=world_tokens,
        world_preface=world_preface,
        rating_name=rating_name,
        story_splitter=story_splitter,
        history=[history_to_dto(h) for h in history_list],
        tokenized_history=[tokenized_history_to_dto(th) for th in tokenized_history_list],
        max_tokenized_history_block=max_tokenized_history_block,
        tokenize_threshold=tokenize_threshold,
        tokenized_history_block_size=tokenized_history_block_size,
        created_at=game.created_at,
        updated_at=game.updated_at,
        deep_history=None  # Will be set by the endpoint
    )

# def convert_history(saved_game_id, history_list):
#     return [
#         StoryHistory(
#             saved_game_id=saved_game_id,
#             text=entry.entry,
#             created_at=datetime.utcnow()
#         )
#         for entry in history_list or []
#     ]

def convert_tokenized_history(saved_game_id, th_list):
    return [
        TokenizedHistory(
            saved_game_id=saved_game_id,
            start_index=th.start_index,
            end_index=th.end_index,
            summary=th.summary,
            created_at=datetime.now(timezone.utc)
        )
        for th in th_list or []
    ]

def serialize_for_json(obj):
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(v) for v in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj