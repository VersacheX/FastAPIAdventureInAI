"""
Story history routes.
Handles CRUD operations for story history with automatic tokenization and compression.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session


from business.schemas import HistoryEntryIn
from business.dtos import HistoryDTO
from business.models import User

from shared.services.orm_service import get_db
from shared.services.auth_service import verify_game_ownership, get_current_user

from api.services.history_service import  (
    perform_create_history_entry,
    perform_delete_history_entry,
    perform_update_history_entry
)

router = APIRouter(prefix="/history", tags=["history"])


@router.post("/", response_model=HistoryDTO, status_code=201)
async def create_history_entry(
    history_data: HistoryEntryIn,
    saved_game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_create_history_entry(history_data,saved_game_id, db, current_user)

@router.delete("/{history_id}", response_model=dict)
async def delete_history_entry(
    history_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_delete_history_entry(history_id, db, current_user)

@router.put("/{history_id}", response_model=HistoryDTO)
async def update_history_entry(
    history_id: int,
    update_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_update_history_entry(history_id, update_data, db, current_user)