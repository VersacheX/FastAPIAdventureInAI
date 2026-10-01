"""
AI directive settings routes.

- GET  /settings/resolve  -> fully-built settings dict consumed by the AI server
- GET  /settings/         -> list raw settings rows (dev app)
- GET  /settings/{id}     -> get a raw settings row (dev app)
- PATCH /settings/{id}    -> update a settings row (dev app)
"""
from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from business.dtos import AIDirectiveSettingsDTO
from shared.services.orm_service import get_db
from shared.services.auth_service import get_current_user
from business.models import User

from api.services.settings_service import (
    perform_resolve_settings,
    perform_get_settings,
    perform_list_settings,
    perform_update_settings,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/resolve")
async def resolve_settings(
    settings_id: Optional[int] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Fully-built settings dict for the AI server. Unauthenticated (LAN trust)."""
    return await perform_resolve_settings(settings_id=settings_id, user_id=user_id, db=db)


@router.get("/", response_model=List[AIDirectiveSettingsDTO])
async def list_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await perform_list_settings(db=db)


@router.get("/{settings_id}", response_model=AIDirectiveSettingsDTO)
async def get_settings(
    settings_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await perform_get_settings(settings_id=settings_id, db=db)


@router.patch("/{settings_id}", response_model=AIDirectiveSettingsDTO)
async def update_settings(
    settings_id: int,
    updates: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await perform_update_settings(settings_id=settings_id, updates=updates, db=db)
