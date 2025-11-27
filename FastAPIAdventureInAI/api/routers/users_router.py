"""
User routes.
Handles user CRUD operations and user-specific queries.
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from business.schemas import UserCreate
from business.dtos import UserDTO, WorldDTO, SavedGameDTO, AccountLevelDTO
from business.models import User
from shared.services.orm_service import get_db
from shared.services.auth_service import get_current_user, get_user_by_username

from api.services.users_service import (
    perform_get_account_level_me,
    perform_create_user,
    perform_get_user,
    perform_get_user_by_username_endpoint,
    perform_list_my_worlds,
    perform_list_user_saved_games
)

router = APIRouter(prefix="/users", tags=["users"])

# Protected endpoint to get current user's AccountLevel and AIDirectiveSettings
@router.get("/account_level/me", response_model=AccountLevelDTO)
async def get_account_level_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_get_account_level_me(db, current_user)

@router.post("/", response_model=UserDTO)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    return await perform_create_user(user, db)


@router.get("/{user_id}", response_model=UserDTO)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    return  await perform_get_user(user_id, db)

@router.get("/by_username/{username}", response_model=UserDTO)
async def get_user_by_username_endpoint(
    username: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_get_user_by_username_endpoint(username, db, current_user)

@router.get("/me/worlds/", response_model=List[WorldDTO])
async def list_my_worlds(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_list_my_worlds(db, current_user)

@router.get("/{user_id}/saved_games/", response_model=List[SavedGameDTO])
async def list_user_saved_games(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_list_user_saved_games(user_id, db, current_user)