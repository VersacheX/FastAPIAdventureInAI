from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class AIDirectiveSettingsDTO(BaseModel):
    id: int
    storyteller_prompt: str
    game_directive: str
    summary_split_marker: str
    stop_tokens: str  # Comma-separated tokens as stored in DB
    recent_memory_limit: int
    memory_backlog_limit: int
    tokenize_history_chunk_size: int
    tokenize_threshold: int
    max_tokenized_history_block: int
    tokenized_history_block_size: int
    deep_memory_max_tokens: int
    summary_min_token_percent: float
    max_tokens: int
    reserved_for_generation: int
    safe_prompt_limit: int
    max_world_tokens: int
    class Config:
        from_attributes = True

class AccountLevelDTO(BaseModel):
    id: int
    name: str
    game_settings: AIDirectiveSettingsDTO
    class Config:
        from_attributes = True

class UserDTO(BaseModel):
    id: int
    username: str
    email: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True

class WorldDTO(BaseModel):
    id: int
    user_id: Optional[int] = None  # NULL for system worlds
    name: str
    preface: str
    world_tokens: str
    created_at: datetime
    updated_at: datetime
    game_count: int = 0
    token_count: Optional[int] = None  # Total tokens for name + preface + world_tokens (None if not calculated)
    class Config:
        from_attributes = True

class GameRatingDTO(BaseModel):
    id: int
    name: str
    ai_prompt: str
    class Config:
        from_attributes = True

class HistoryDTO(BaseModel):
    id: int
    saved_game_id: int
    entry_index: int
    text: str = Field(..., alias="entry")  # Model uses 'text', API uses 'entry'
    token_count: Optional[int] = None
    is_tokenized: bool = Field(default=False)

    class Config:
        from_attributes = True
        populate_by_name = True  # Allow using both 'entry' and 'text'

class TokenizedHistoryDTO(BaseModel):
    id: int
    saved_game_id: int
    start_index: int
    end_index: int
    summary: str
    token_count: Optional[int] = None
    history_references: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class DeepMemoryDTO(BaseModel):
    id: int
    saved_game_id: int
    summary: str
    token_count: Optional[int] = None
    chunks_merged: Optional[int] = None
    last_merged_end_index: Optional[int] = None
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True
        
class SavedGameDTO(BaseModel):
    id: int
    user_id: int
    world_id: int
    rating_id: int
    player_name: str
    player_gender: str
    history_count: int
    world_name: str
    world_tokens: str
    world_preface: str
    rating_name: str
    story_splitter: str
    history: List[HistoryDTO]
    tokenized_history: Optional[List[TokenizedHistoryDTO]] = None
    max_tokenized_history_block: int = 6
    tokenize_threshold: int = 800
    tokenized_history_block_size: int = 200
    created_at: datetime
    updated_at: datetime
    deep_history: Optional[List[DeepMemoryDTO]] = None
    class Config:
        from_attributes = True
