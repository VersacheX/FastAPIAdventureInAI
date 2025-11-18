"""
AI service layer - AI server integration, settings, and schemas.
"""
from ai.ai_settings import (
    get_ai_settings,
    get_setting,
    get_storyteller_prompt,
    get_game_directive,
    get_stop_tokens,
    get_memory_limits
)
from ai.ai_client_requests import (
    ai_prime_narrator,
    ai_generate_story,
    ai_count_tokens,
    ai_summarize_chunk
)
from ai.schemas_ai_server import (
    GenerateStoryRequest,
    GenerateFromGameRequest,
    SummarizeChunkRequest
)
from ai.ai_helpers import (
    get_recent_memories,
    build_structured_json,
    generate_story,
    tokenize_history,
    summarize_chunk
)

__all__ = [
    # Settings
    "get_ai_settings",
    "get_setting",
    "get_storyteller_prompt",
    "get_game_directive",
    "get_stop_tokens",
    "get_memory_limits",
    # Client requests
    "ai_prime_narrator",
    "ai_generate_story",
    "ai_count_tokens",
    "ai_summarize_chunk",
    # Schemas
    "GenerateStoryRequest",
    "GenerateFromGameRequest",
    "SummarizeChunkRequest",
    # Helpers
    "get_recent_memories",
    "build_structured_json",
    "generate_story",
    "tokenize_history",
    "summarize_chunk"
]
