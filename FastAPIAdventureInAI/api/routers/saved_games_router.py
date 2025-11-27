"""
Saved games routes.
Handles CRUD operations for saved games and related game statistics.
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from business.schemas import SavedGameCreate, SavedGameIdResponse
from business.dtos import SavedGameDTO, TokenizedHistoryDTO
from business.models import User
from shared.services.orm_service import get_db
from shared.services.auth_service import verify_game_ownership, get_current_user

from api.services.saved_games_service import (
    perform_get_saved_game,
    perform_list_tokenized_history,
    perform_get_deep_memory,
    perform_get_token_stats,
    perform_update_saved_game,
    perform_create_saved_game,
    perform_delete_saved_game
)

router = APIRouter(prefix="/saved_games", tags=["saved games"])


@router.get("/{game_id}", response_model=SavedGameDTO)
async def get_saved_game(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_get_saved_game(game_id, db, current_user)

@router.get("/{game_id}/tokenized_history/", response_model=List[TokenizedHistoryDTO])
async def list_tokenized_history(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_list_tokenized_history(game_id, db, current_user)

@router.get("/{game_id}/deep_memory/")
async def get_deep_memory(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_get_deep_memory(game_id, db, current_user)

@router.get("/{game_id}/token_stats")
async def get_token_stats(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_get_token_stats(game_id, db, current_user)

@router.put("/{game_id}", response_model=SavedGameDTO)
async def update_saved_game(
    game_id: int,
    game_data: SavedGameCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_update_saved_game(game_id, game_data, db, current_user)

@router.post("/", response_model=SavedGameIdResponse, status_code=201)
async def create_saved_game(
    game_data: SavedGameCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_create_saved_game(game_data, db, current_user)

@router.delete("/{game_id}", response_model=dict)
async def delete_saved_game(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_delete_saved_game(game_id, db, current_user)
