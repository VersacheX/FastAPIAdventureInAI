from pydantic import BaseModel
from typing import Optional, List, Dict

class GenerateStoryRequest(BaseModel):
    context: Dict
    user_input: Optional[str] = ""
    include_initial: Optional[bool] = False

class GenerateFromGameRequest(BaseModel):
    player_name: str
    player_gender: str
    world_name: str
    world_tokens: Optional[str] = ""
    rating_name: str
    story_splitter: Optional[str] = "###"
    story_preface: Optional[str] = ""
    history: List[str]
    tokenized_history: List[Dict]
    deep_memory: Optional[str] = None
    user_input: str
    action_mode: Optional[str] = "ACTION"
    include_initial: Optional[bool] = False

class SummarizeChunkRequest(BaseModel):
    chunk: List[str]
    max_tokens: int
    previous_summary: Optional[str] = None
