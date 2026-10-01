import random
import re
import json
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool
from llama_cpp import Llama

from ai.schemas_ai_server import (
    PopulatePrimaryStorySettingsRequest,
    TaskAuthoringRequest,
    TaskAuthoringResponse,
)
from ai.services.authoring_modeler_service import (
    get_authoring_model,
    generate_authoring_json,
)
from shared.helpers.ai_settings import get_user_ai_settings
from shared.services.auth_service import get_current_user


router = APIRouter(tags=["authoring"])


def _cleanup_generated_python_block(text: str) -> str:
    # remove markdown fences if the model outputs them
    text = re.sub(r"^```[a-zA-Z0-9_+-]*\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    return text.strip()


def _extract_json_from_output(text: str) -> Dict[str, Any]:
    """Extract JSON from AI output, handling
   markdown fences and common artifacts."""
    # Remove markdown JSON fences
    text = re.sub(r"^```json\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    
    # Try to find JSON object/array
    json_match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from AI output: {e}\nOutput was: {text[:500]}")


def _build_event_catalog() -> str:
    """Return a compact event catalog for the AI to reference."""
    return """
ALLOWED EVENT TYPES (use exact event_type names):
- initiate_dialog: params {npc_id, dialog_id}
- initiate_character_dialog: params {npc_id, dialog_id} (npc_id must be: technique|tech|magic|faith|skill)
- create_npc: params {npc_id, location}
- hide_npc: params {npc_id}
- show_npc: params {npc_id, location}
- set_npc_met: params {npc_id}
- set_npc_standing_text: params {npc_id, standing_text: [list of strings]}
- award_task: params {task_id}
- award_money: params {amount: int}
- award_item: params {item_id, quantity?: int}
- remove_item: params {item_id, quantity?: int}
- create_dungeon: params {dungeon_id, location}
- lock_dungeon: params {dungeon_id}
- unlock_dungeon: params {dungeon_id}
- set_dungeon_locked_text: params {dungeon_id, locked_text: [list of strings]}
- dungeon_add_npc: params {dungeon_id, npc_id, location}
- dungeon_add_treasure: params {dungeon_id, item_id, location}
- begin_combat: params {boss_mob_id, combat_type}
- set_player_in_dungeon: params {dungeon_id, location}
- remove_player_from_dungeon: params {dungeon_id}
- set_aircraft: params {location}
- advance_chapter: no params
- player_character_join: params {dialog_id}
- add_pending_character: no params
- create_character_npc: params {location}
- complete_intro_story: no params

LOCATION NAMING RULES:
- Use 'region_' + tile_type (e.g., 'region_open_area', 'region_city_bar', 'region_city_inn')
- Tile types: open_area, bar, inn, shopweapons, shopitems, shoparmor, residencelarge, residencesmall, businesslarge, businesssmall, subway, other1, other2
- For specific cities: 'city_index_##' or 'city_index_##_region' or '{biome}_{city_size}' (e.g., 'desert_large_city')
- Biomes: desert, grassland, shallows, mountains, swamp, snow, forest
- City sizes: large_city, mid_city, small_city

PLAYER CHARACTER NPC IDs (for initiate_character_dialog):
- technique, tech, magic, faith, skill
"""


def _build_task_schema_prompt() -> str:
    """Return task object schema for the AI."""
    return """
TASK OBJECT SCHEMA:
{
  "task_id": "string (snake_case)",
  "type": "deliver|meet|defeat|complete_intro_story",
  "item_id": "string (only for deliver type)",
  "to_type": "npc|mob (required for meet/deliver/defeat)",
  "to_id": "string (required for meet/deliver/defeat)",
  "task_acquire_events": [ EVENT_OBJECTS ],
  "task_complete_events": [ EVENT_OBJECTS ]
}

EVENT OBJECT SCHEMA:
{
  "event_type": "string (from allowed list)",
  "params": { key-value pairs as specified in catalog }
}

RULES:
- deliver tasks MUST have item_id, to_type, to_id
- meet/defeat tasks MUST have to_type, to_id
- complete_intro_story tasks ONLY have task_id
- All task_ids must be unique and snake_case
- All npc_ids, item_ids, dungeon_ids referenced in events must exist or be created earlier in the chain
"""


def _build_mode_prompt(mode: str, request: TaskAuthoringRequest) -> str:
    """Build specialized prompt based on mode."""
    base = (
        f"You are generating content for chapter '{request.chapter_id}'.\n\n"
        f"USER REQUIREMENTS:\n{request.prompt.strip()}\n\n"
        f"SOURCE TEXT:\n{request.text_input.strip()}\n\n"
    )
    
    if mode == "plan":
        return (
            f"{base}"
            f"OUTPUT REQUIREMENT: Return ONLY a JSON object with this structure:\n"
            f"{{\n"
            f'  "tasks": [\n'
            f'    {{"task_id": "string", "type": "meet|deliver|defeat|complete_intro_story", "depends_on": ["prior_task_ids"]}}\n'
            f'  ]\n'
            f"}}\n\n"
            f"Generate a high-level plan for tasks. Keep it to 6-10 tasks max.\n"
            f"Focus on: task_id, type, and dependencies (which tasks must complete before this one).\n"
            f"Return ONLY the JSON object. No markdown, no explanation.\n"
        )
    
    elif mode == "npcs":
        known = ", ".join(request.known_npc_ids) if request.known_npc_ids else "none"
        return (
            f"{base}"
            f"Known NPC IDs already defined: {known}\n\n"
            f"OUTPUT REQUIREMENT: Return ONLY a JSON object:\n"
            f"{{\n"
            f'  "npcs": [\n'
            f'    {{"npc_id": "string", "name": "string", "description": "string"}}\n'
            f'  ]\n'
            f"}}\n\n"
            f"Generate NPC definitions. Limit to 5 NPCs.\n"
            f"npc_id must be snake_case and unique.\n"
            f"description should be 1-3 sentences.\n"
            f"Return ONLY the JSON object. No markdown, no explanation.\n"
        )
    
    elif mode == "dialog":
        known_npcs = ", ".join(request.known_npc_ids) if request.known_npc_ids else "none"
        target = f" for npc_id={request.target_npc_id}" if request.target_npc_id else ""
        return (
            f"{base}"
            f"Known NPC IDs: {known_npcs}\n"
            f"Player character NPC IDs: technique, tech, magic, faith, skill\n\n"
            f"OUTPUT REQUIREMENT: Return ONLY a JSON object:\n"
            f"{{\n"
            f'  "npc_dialog": [\n'
            f'    {{"npc_id": "string", "dialog_id": "string", "dialog": ["line1", "line2", ...]}}\n'
            f'  ]\n'
            f"}}\n\n"
            f"Generate dialog entries{target}. Limit to 5 dialog objects.\n"
            f"npc_id must reference existing NPCs or player characters (technique/tech/magic/faith/skill).\n"
            f"dialog_id must be snake_case and unique.\n"
            f"dialog array should have 2-5 lines.\n"
            f"Return ONLY the JSON object. No markdown, no explanation.\n"
        )
    
    elif mode == "tasks":
        known_npcs = ", ".join(request.known_npc_ids) if request.known_npc_ids else "none"
        known_items = ", ".join(request.known_item_ids) if request.known_item_ids else "none"
        known_dungeons = ", ".join(request.known_dungeon_ids) if request.known_dungeon_ids else "none"
        known_dialogs = ", ".join(request.known_dialog_ids) if request.known_dialog_ids else "none"
        
        return (
            f"{base}"
            f"{_build_event_catalog()}\n"
            f"{_build_task_schema_prompt()}\n\n"
            f"KNOWN ENTITIES:\n"
            f"- NPCs: {known_npcs}\n"
            f"- Items: {known_items}\n"
            f"- Dungeons: {known_dungeons}\n"
            f"- Dialog IDs: {known_dialogs}\n\n"
            f"OUTPUT REQUIREMENT: Return ONLY a JSON object:\n"
            f"{{\n"
            f'  "tasks": [ TASK_OBJECTS ]\n'
            f"}}\n\n"
            f"Generate {request.max_tasks or 5} task objects following the TASK OBJECT SCHEMA.\n"
            f"Ensure all referenced npc_ids, item_ids, dungeon_ids, dialog_ids exist in known entities or are created via events.\n"
            f"Return ONLY the JSON object. No markdown, no explanation.\n"
        )
    
    else:
        raise ValueError(f"Unknown mode: {mode}")


def _validate_task_output(data: Dict[str, Any], request: TaskAuthoringRequest) -> List[str]:
    """Validate task output and return warnings."""
    warnings = []
    
    if request.mode == "tasks":
        tasks = data.get("tasks", [])
        for i, task in enumerate(tasks):
            if not isinstance(task, dict):
                warnings.append(f"Task {i} is not a dict")
                continue
            
            if "task_id" not in task:
                warnings.append(f"Task {i} missing task_id")
            
            task_type = task.get("type")
            if task_type not in ["deliver", "meet", "defeat", "complete_intro_story"]:
                warnings.append(f"Task {task.get('task_id', i)} has invalid type: {task_type}")
            
            if task_type == "deliver" and "item_id" not in task:
                warnings.append(f"Task {task.get('task_id', i)} (deliver) missing item_id")
            
            if task_type in ["deliver", "meet", "defeat"]:
                if "to_type" not in task or "to_id" not in task:
                    warnings.append(f"Task {task.get('task_id', i)} ({task_type}) missing to_type or to_id")
            
            # Validate events reference known entities
            for event_list_key in ["task_acquire_events", "task_complete_events"]:
                events = task.get(event_list_key, [])
                for j, event in enumerate(events):
                    if not isinstance(event, dict):
                        warnings.append(f"Task {task.get('task_id', i)} {event_list_key}[{j}] is not a dict")
                        continue
                    
                    event_type = event.get("event_type")
                    params = event.get("params", {})
                    
                    # Check if npc_id exists in known list
                    if "npc_id" in params:
                        npc_id = params["npc_id"]
                        if npc_id not in (request.known_npc_ids or []) and npc_id not in ["technique", "tech", "magic", "faith", "skill", "pending_character"]:
                            warnings.append(f"Task {task.get('task_id', i)} references unknown npc_id: {npc_id}")
    
    return warnings


@router.post("/authoring/populate_primary_story_settings/")
async def populate_primary_story_settings(
    request: PopulatePrimaryStorySettingsRequest,
    user=Depends(get_current_user),
    llm: Llama = Depends(get_authoring_model),
):
    settings = get_user_ai_settings(user.id)

    max_new_tokens = request.max_new_tokens or settings.get("RESERVED_FOR_GENERATION", 900)

    # Hard constrain output to your desired python-literal format
    directive = (
        "Return ONLY valid Python code. No markdown. No explanations.\n"
        "The output MUST be exactly these top-level variables:\n"
        "ATTAINABLE_PLAYER_CHARACTERS = [...]\n"
        "NPCS = [...]\n"
        "NPC_DIALOG = [...]\n"
        "TASKS = [...]\n"
        "PRIMARY_STORY_SETTINGS = {\n"
        "    'chapter_id': '<chapter_id>',\n"
        "    'tasks': TASKS,\n"
        "    'npcs': NPCS,\n"
        "    'npc_dialog': NPC_DIALOG,\n"
        "    'attainable_player_characters': ATTAINABLE_PLAYER_CHARACTERS,\n"
        "}\n"
        "Use single quotes for strings. Keep IDs snake_case. Ensure lists/dicts are syntactically valid.\n"
    )

    user_prompt = (
        f"chapter_id = '{request.chapter_id}'\n\n"
        f"USER_PROMPT:\n{request.prompt.strip()}\n\n"
        f"TEXT_INPUT:\n{request.text_input.strip()}\n\n"
        f"BEGIN PYTHON OUTPUT:\n"
    )

    text = await run_in_threadpool(
        lambda: generate_authoring_json(
            llm,
            system_prompt=directive,
            user_prompt=user_prompt,
            max_tokens=max_new_tokens,
            temperature=0.4,
            top_p=0.9,
            force_json=False,
        )
    )

    # optional: apply your existing stop tokens if present
    for stop_token in settings.get("STOP_TOKENS", ""):
        if text.strip().startswith(stop_token):
            text = text.strip()[len(stop_token):].lstrip()

    text = _cleanup_generated_python_block(text)

    return {
        "chapter_id": request.chapter_id,
        "primary_story_settings": text,
    }


@router.post("/authoring/task_authoring/", response_model=TaskAuthoringResponse)
async def task_authoring(
    request: TaskAuthoringRequest,
    user=Depends(get_current_user),
    llm: Llama = Depends(get_authoring_model),
):
    """
    Modular task authoring endpoint with multiple modes:
    - plan: Generate high-level task plan
    - npcs: Generate NPC definitions
    - dialog: Generate dialog entries
    - tasks: Generate full task objects with events
    """
    if request.mode not in ["plan", "npcs", "dialog", "tasks"]:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {request.mode}")

    settings = get_user_ai_settings(user.id)

    # Adjust max_new_tokens based on mode
    if request.max_new_tokens:
        max_new_tokens = request.max_new_tokens
    elif request.mode == "plan":
        max_new_tokens = 600
    elif request.mode == "npcs":
        max_new_tokens = 800
    elif request.mode == "dialog":
        max_new_tokens = 800
    elif request.mode == "tasks":
        max_new_tokens = 1200
    else:
        max_new_tokens = 800

    prompt = _build_mode_prompt(request.mode, request)

    system_prompt = (
        "You are a structured content generator for a text adventure authoring tool. "
        "Follow the output requirements exactly and return only a single valid JSON object."
    )

    # Log prompt for debugging
    print(f"\n{'='*80}")
    print(f"TASK AUTHORING MODE: {request.mode}")
    print(f"{'='*80}")
    print(f"Prompt length: {len(prompt)} chars")
    print(f"Max new tokens: {max_new_tokens}")
    print(f"{'='*80}\n")

    text = await run_in_threadpool(
        lambda: generate_authoring_json(
            llm,
            system_prompt=system_prompt,
            user_prompt=prompt,
            max_tokens=max_new_tokens,
            temperature=0.3,  # Lower temp for more structured output
            top_p=0.9,
            force_json=True,
        )
    )

    print(f"\n{'='*80}")
    print(f"RAW AI OUTPUT:")
    print(f"{'='*80}")
    print(text[:1000])
    print(f"{'='*80}\n")

    # Parse JSON output
    try:
        data = _extract_json_from_output(text)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Validate output
    warnings = _validate_task_output(data, request)

    return TaskAuthoringResponse(
        mode=request.mode,
        chapter_id=request.chapter_id,
        data=data,
        warnings=warnings if warnings else None
    )