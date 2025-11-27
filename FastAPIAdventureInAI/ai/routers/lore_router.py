from typing import Tuple
from fastapi import APIRouter, Depends
from ai.schemas_ai_server import LoreRetrieveRequest
from ai.services.ai_modeler_service import get_model
from shared.services.auth_service import get_current_user
from ai.services.lookup_ai_service import describe_entity_ai


router = APIRouter(tags=["authentication"])

@router.post("/lore/retrieve_tokens")
async def lore_retrieve_tokens(request: LoreRetrieveRequest, user=Depends(get_current_user), model_and_tokenizer: Tuple = Depends(get_model)):
    """Retrieve external lore draft tokens based solely on the user lookup prompt.

    Ignores story/world preface intentionally to avoid diluting query focus.
    Non-invasive: does not modify any persistent state. Returns structured draft for user approval.
    """
    lookup_text = request.lookup_prompt.strip()
    command_prompt = (request.command_prompt or "").strip()
    meta_data = (request.meta_data or "").strip()
    
    generator, tokenizer = model_and_tokenizer
    # Pass command_prompt through to describer so client can influence response format
    desc = await describe_entity_ai(lookup_text, user, tokenizer, generator, command_prompt=command_prompt or None, meta_data=meta_data or None)

    return desc