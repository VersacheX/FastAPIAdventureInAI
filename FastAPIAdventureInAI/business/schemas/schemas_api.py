from pydantic import BaseModel
from typing import Optional, List, Dict

class UserCreate(BaseModel):
    username: str
    password: str

class UserRegister(BaseModel):
    username: str
    password: str
    email: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str


class HistoryEntryIn(BaseModel):
    """Single-history-entry payload used by the client when posting one entry."""
    entry: str

class HistoryIn(BaseModel):
    game_id: str
    history: List[str]
    entry: str

class TokenizedHistoryIn(BaseModel):
    game_id: str
    tokenized_history: List[Dict]
    start_index: int
    end_index: int
    summary: str

class SavedGameCreate(BaseModel):
    player_name: str
    world_name: str
    rating_name: str
    history: List[str]
    tokenized_history: List[Dict]
    deep_memory: Optional[str] = None

class SavedGameIdResponse(BaseModel):
    game_id: str

class DeepMemoryCreate(BaseModel):
    saved_game_id: int
    summary: str = ""

class DeepMemoryUpdate(BaseModel):
    summary: str