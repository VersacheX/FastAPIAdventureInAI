"""
Tokenized history routes.
Handles compressed chunks of story history for memory efficiency.
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session


from business.schemas import TokenizedHistoryIn
from business.dtos import TokenizedHistoryDTO
from business.models import User
from shared.services.orm_service import get_db
from shared.services.auth_service import verify_game_ownership, get_current_user

from api.services.tokenized_history_service import (
    perform_create_tokenized_history_entry,
    perform_update_tokenized_history_entry,
    perform_delete_tokenized_history_entry
)

router = APIRouter(prefix="/tokenized_history", tags=["tokenized history"])


@router.post("/", response_model=TokenizedHistoryDTO, status_code=201)
async def create_tokenized_history_entry(
    th_data: TokenizedHistoryIn,
    saved_game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_create_tokenized_history_entry(th_data, saved_game_id, db, current_user)

@router.put("/{tokenized_id}", response_model=TokenizedHistoryDTO)
async def update_tokenized_history_entry(
    tokenized_id: int,
    update_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_update_tokenized_history_entry(tokenized_id, update_data, db, current_user)

@router.delete("/{tokenized_id}")
async def delete_tokenized_history_entry(
    tokenized_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_delete_tokenized_history_entry(tokenized_id, db, current_user)