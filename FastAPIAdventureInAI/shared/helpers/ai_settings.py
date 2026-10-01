"""
Helper module to load AI directive settings from the database.
This replaces hardcoded constants from aiadventureinpythonconstants.py
Settings can be loaded per user account level (Basic/Elite tiers).
"""

from typing import Optional
from business.models import User
from business.models import AIDirectiveSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Cache for settings to avoid repeated DB queries
# Key: settings_id, Value: settings dict
global _settings_cache
_settings_cache = {}    

# TTL (seconds) for remotely-fetched settings. The remote cache lives in the
# AI-server process and cannot be invalidated directly by the data server, so a
# short TTL bounds how long a cross-process settings edit can go unseen.
_REMOTE_CACHE_TTL_SECONDS = 60


def _default_ai_settings():
    """Assemble an AI settings dict from the hardcoded constants module.

    Used as a fallback when the database is unreachable (e.g. the AI/GPU box
    running in WSL without SQL Server access). This lets the AI server operate
    as a pure inference engine with no database dependency.
    """
    import aiadventureinpythonconstants as C
    return {
        'STORYTELLER_PROMPT': C.STORYTELLER_PROMPT,
        'GAME_DIRECTIVE': C.GAME_DIRECTIVE,
        'SUMMARY_SPLIT_MARKER': C.SUMMARY_SPLIT_MARKER,
        'STOP_TOKENS': list(C.STOP_TOKENS),
        'RECENT_MEMORY_LIMIT': C.RECENT_MEMORY_LIMIT,
        'MEMORY_BACKLOG_LIMIT': C.MEMORY_BACKLOG_LIMIT,
        'TOKENIZE_HISTORY_CHUNK_SIZE': C.TOKENIZE_HISTORY_CHUNK_SIZE,
        'TOKENIZE_THRESHOLD': C.TOKENIZE_THRESHOLD,
        'MAX_TOKENIZED_HISTORY_BLOCK': C.MAX_TOKENIZED_HISTORY_BLOCK,
        'TOKENIZED_HISTORY_BLOCK_SIZE': C.TOKENIZED_HISTORY_BLOCK_SIZE,
        'SUMMARY_MIN_TOKEN_PERCENT': C.SUMMARY_MIN_TOKEN_PERCENT,
        'DEEP_MEMORY_MAX_TOKENS': C.DEEP_MEMORY_MAX_TOKENS,
        'MAX_TOKENS': C.MAX_TOKENS,
        'RESERVED_FOR_GENERATION': C.RESERVED_FOR_GENERATION,
        'SAFE_PROMPT_LIMIT': C.SAFE_PROMPT_LIMIT,
        'MAX_WORLD_TOKENS': C.MAX_WORLD_TOKENS,
        'SAFE_PROMPT_LIMIT_COMPUTED': C.MAX_TOKENS - C.RESERVED_FOR_GENERATION,
    }


def get_user_ai_settings(user_id: int):
    return get_ai_settings(None, None, user_id)


async def get_user_ai_settings_async(user_id: int):
    """Async wrapper around get_user_ai_settings for use in async routes.

    Settings resolution can perform a synchronous, blocking HTTP call to the
    data server (remote mode) plus a potential DB fallback. Running that inline
    in an async endpoint would block the event loop for up to the request
    timeout and stall unrelated inference requests, so offload it to a worker
    thread.
    """
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(get_user_ai_settings, user_id)


def invalidate_settings_cache():
    """Clear the in-process AI settings cache.

    Must be called after a settings row is updated so subsequent reads (and the
    AI server's remote fetches) pick up the new values instead of stale cached
    ones.
    """
    global _settings_cache
    _settings_cache.clear()


def get_ai_settings(db = None, settings_id: int = None, user_id: int = None, force_reload: bool = False):
    """
    Load AI directive settings.

    Resolution order:
    1. Remote data server over HTTP (if SETTINGS_REMOTE_URL is configured). This
       is how the AI server in WSL gets DB-backed settings without SQL access.
    2. Direct database read (used by the data server itself).
    3. Hardcoded constants fallback (only if both of the above fail).

    Priority for which settings row:
    1. If settings_id provided, load that specific settings
    2. If user_id provided, load settings based on user's account level
    3. Otherwise, load default settings (ID=1, Basic)

    Settings are cached after first load unless force_reload=True.
    """
    import sys
    from config import SETTINGS_REMOTE_URL

    # 1. Remote fetch (AI server in WSL)
    if SETTINGS_REMOTE_URL:
        try:
            return _get_ai_settings_from_remote(settings_id, user_id, force_reload)
        except Exception as e:
            print(f"[ai_settings] WARNING: remote settings fetch failed: {e}", file=sys.stderr)

    # 2. Direct database read (data server)
    try:
        return _get_ai_settings_from_db(db, settings_id, user_id, force_reload)
    except Exception as e:
        print(f"[ai_settings] WARNING: falling back to constants (DB unavailable): {e}", file=sys.stderr)

    # 3. Constants fallback
    return _default_ai_settings()


def _get_ai_settings_from_remote(settings_id: int = None, user_id: int = None, force_reload: bool = False):
    """Fetch the fully-built settings dict from the data server over HTTP."""
    import time
    import requests
    from config import SETTINGS_REMOTE_URL

    cache_key = ("remote", settings_id, user_id)
    # The remote cache lives in THIS (AI-server) process, while the data server
    # invalidates its own cache on PATCH. To make cross-process edits propagate
    # without a long-lived stale value, remote entries carry a short TTL and are
    # re-fetched once expired.
    cached = _settings_cache.get(cache_key)
    if cached and not force_reload:
        value, expires_at = cached
        if time.monotonic() < expires_at:
            return value

    params = {}
    if settings_id is not None:
        params["settings_id"] = settings_id
    if user_id is not None:
        params["user_id"] = user_id

    url = SETTINGS_REMOTE_URL.rstrip("/") + "/settings/resolve"
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    settings_dict = resp.json()

    # STOP_TOKENS may arrive as a list already; leave as-is.
    _settings_cache[cache_key] = (settings_dict, time.monotonic() + _REMOTE_CACHE_TTL_SECONDS)
    return settings_dict


def _get_ai_settings_from_db(db = None, settings_id: int = None, user_id: int = None, force_reload: bool = False):

    # Determine which settings to load
    if settings_id is None and user_id is not None:
        # Load user's account level settings
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
            'DEEP_MEMORY_MAX_TOKENS': settings.deep_memory_max_tokens,
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
