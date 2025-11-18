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
    user_id: int
    world_id: int
    rating_id: int
    player_name: str
    player_gender: str
    history: Optional[List[HistoryEntryIn]] = None
    tokenized_history: Optional[List[Dict]] = None

class SavedGameIdResponse(BaseModel):
    id: int  # Changed from game_id to match endpoint response

class DeepMemoryCreate(BaseModel):
    saved_game_id: int
    summary: str = ""

class DeepMemoryUpdate(BaseModel):
    summary: str