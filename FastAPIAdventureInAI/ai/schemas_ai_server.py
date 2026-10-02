from pydantic import BaseModel
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

class DeepSummarizeChunkRequest(BaseModel):
    chunk: str
    max_tokens: int
    previous_summary: Optional[str] = None

class LoreRetrieveRequest(BaseModel):
    lookup_prompt: str
    story_preface: Optional[str] = None
    command_prompt: Optional[str] = None
    meta_data: Optional[str] = None

class PopulatePrimaryStorySettingsRequest(BaseModel):
    chapter_id: str
    prompt: str
    text_input: str
    max_new_tokens: Optional[int] = None

class TaskAuthoringRequest(BaseModel):
    mode: str  # plan | npcs | dialog | tasks
    chapter_id: str
    prompt: str
    text_input: str
    max_new_tokens: Optional[int] = None
    max_tasks: Optional[int] = None
    target_npc_id: Optional[str] = None
    known_npc_ids: Optional[List[str]] = []
    known_item_ids: Optional[List[str]] = []
    known_dungeon_ids: Optional[List[str]] = []
    known_dialog_ids: Optional[List[str]] = []

class TaskAuthoringResponse(BaseModel):
    mode: str
    chapter_id: str
    data: Dict
    warnings: Optional[List[str]] = None
