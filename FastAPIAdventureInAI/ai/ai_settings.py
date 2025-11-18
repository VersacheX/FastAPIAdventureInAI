"""
Helper module to load AI directive settings from the database.
This replaces hardcoded constants from aiadventureinpythonconstants.py
Settings can be loaded per user account level (Basic/Elite tiers).
"""

from typing import Optional

# Cache for settings to avoid repeated DB queries
# Key: settings_id, Value: settings dict
_settings_cache = {}

def get_ai_settings(db = None, settings_id: int = None, user_id: int = None, force_reload: bool = False):
    """
    Load AI directive settings from database.
    
    Priority:
    1. If settings_id provided, load that specific settings
    2. If user_id provided, load settings based on user's account level
    3. Otherwise, load default settings (ID=1, Basic)
    
    If db session is not provided, creates one temporarily.
    Settings are cached after first load unless force_reload=True.
    """
    global _settings_cache
    
    # Determine which settings to load
    if settings_id is None and user_id is not None:
        # Load user's account level settings
        from business.models import User
        need_close = False
        if db is None:
            db, need_close = _get_db_session()
        
        try:
            user = db.query(User).filter_by(id=user_id).first()
            if user and user.account_level:
                settings_id = user.account_level.game_settings_id
            else:
                settings_id = 1  # Default to Basic
        finally:
            if need_close:
                db.close()
    
    if settings_id is None:
        settings_id = 1  # Default to Basic
    
    # Check cache
    cache_key = settings_id
    if cache_key in _settings_cache and not force_reload:
        return _settings_cache[cache_key]
    
    # Import here to avoid circular imports
    from business.models import AIDirectiveSettings
    
    need_close = False
    if db is None:
        db, need_close = _get_db_session()
    
    try:
        settings = db.query(AIDirectiveSettings).filter_by(id=settings_id).first()
        if not settings:
            # Fallback to any settings
            settings = db.query(AIDirectiveSettings).first()
            if not settings:
                raise RuntimeError("No AI directive settings found in database. Run seed_data.py first.")
        
        # Parse stop_tokens from comma-separated string
        stop_tokens = [token.strip() for token in settings.stop_tokens.split(',')]
        
        # Create settings object
        settings_dict = {
            'STORYTELLER_PROMPT': settings.storyteller_prompt,
            'GAME_DIRECTIVE': settings.game_directive,
            'SUMMARY_SPLIT_MARKER': settings.summary_split_marker,
            'STOP_TOKENS': stop_tokens,
            'RECENT_MEMORY_LIMIT': settings.recent_memory_limit,
            'MEMORY_BACKLOG_LIMIT': settings.memory_backlog_limit,
            'TOKENIZE_HISTORY_CHUNK_SIZE': settings.tokenize_history_chunk_size,
            'TOKENIZE_THRESHOLD': settings.tokenize_threshold,
            'MAX_TOKENIZED_HISTORY_BLOCK': settings.max_tokenized_history_block,
            'TOKENIZED_HISTORY_BLOCK_SIZE': settings.tokenized_history_block_size,
            'SUMMARY_MIN_TOKEN_PERCENT': settings.summary_min_token_percent,
            'MAX_TOKENS': settings.max_tokens,
            'RESERVED_FOR_GENERATION': settings.reserved_for_generation,
            'SAFE_PROMPT_LIMIT': settings.safe_prompt_limit,
            'MAX_WORLD_TOKENS': settings.max_world_tokens,
            # Computed value
            'SAFE_PROMPT_LIMIT_COMPUTED': settings.max_tokens - settings.reserved_for_generation
        }
        
        _settings_cache[cache_key] = settings_dict
        return settings_dict
    finally:
        if need_close:
            db.close()

def _get_db_session():
    """Create a temporary database session. Returns (session, need_close)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    # Import DATABASE_URL from api.py or define it here
    # For now, using the connection string directly
    DATABASE_URL = "mssql+pyodbc://sljackson:themagicwordmotherfucker@DESKTOP-3K6IPDC/AIAdventureInPython?driver=ODBC+Driver+17+for+SQL+Server"
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal(), True

def get_setting(key: str, db = None, settings_id: int = None, user_id: int = None):
    """Get a single setting value by key."""
    settings = get_ai_settings(db, settings_id=settings_id, user_id=user_id)
    return settings.get(key)

# Convenience accessors for commonly used settings
def get_storyteller_prompt(db = None, settings_id: int = None, user_id: int = None):
    return get_setting('STORYTELLER_PROMPT', db, settings_id=settings_id, user_id=user_id)

def get_game_directive(db = None, settings_id: int = None, user_id: int = None):
    return get_setting('GAME_DIRECTIVE', db, settings_id=settings_id, user_id=user_id)

def get_stop_tokens(db = None, settings_id: int = None, user_id: int = None):
    return get_setting('STOP_TOKENS', db, settings_id=settings_id, user_id=user_id)

def get_memory_limits(db = None, settings_id: int = None, user_id: int = None):
    settings = get_ai_settings(db, settings_id=settings_id, user_id=user_id)
    return {
        'recent': settings['RECENT_MEMORY_LIMIT'],
        'backlog': settings['MEMORY_BACKLOG_LIMIT'],
        'chunk_size': settings['TOKENIZE_HISTORY_CHUNK_SIZE'],
        'max_blocks': settings['MAX_TOKENIZED_HISTORY_BLOCK'],
        'block_size': settings['TOKENIZED_HISTORY_BLOCK_SIZE']
    }
