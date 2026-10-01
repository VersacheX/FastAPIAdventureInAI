"""
Authentication routes.
Handles user registration and login (JWT token generation).
"""
from fastapi import APIRouter, Depends
from fastapi.requests import Request
from shared.services.auth_service import verify_token
from ai.services.ai_modeler_service import get_model
from ai.services.ai_api_service import perform_count_tokens

router = APIRouter(tags=["authentication"])

@router.post("/tokens/count_tokens/")
async def count_tokens(request: Request, username: str = Depends(verify_token), engine = Depends(get_model)):
    return await perform_count_tokens(request, engine)

@router.post("/tokens/count_tokens_batch/")
async def count_tokens_batch(request: Request, username: str = Depends(verify_token), engine = Depends(get_model)):
    """Count tokens for multiple texts."""
    body = await request.json()
    texts = body.get("texts", [])

    token_counts = []
    for text in texts:
        token_counts.append(engine.count_tokens(text))

    return {"token_counts": token_counts}