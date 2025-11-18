"""
User routes.
Handles user CRUD operations and user-specific queries.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dependencies import get_db, get_current_user, get_user_by_username
from business.schemas import UserCreate
from business.dtos import UserDTO, WorldDTO, SavedGameDTO
from business.models import User, World, SavedGame, StoryHistory, GameRating
from business.converters import user_to_dto, world_to_dto

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserDTO)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user.
    Note: For authentication/registration, use the /register endpoint instead.
    """
    db_user = User(username=user.username, email=user.email)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.get("/{user_id}", response_model=UserDTO)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user_to_dto(user)


@router.get("/by_username/{username}", response_model=UserDTO)
async def get_user_by_username_endpoint(
    username: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get user by username.
    Requires authentication.
    """
    user = get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/me/worlds/", response_model=List[WorldDTO])
async def list_my_worlds(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all worlds belonging to the current authenticated user."""
    worlds = db.query(World).filter(World.user_id == current_user.id).all()
    return [world_to_dto(w, calculate_tokens=True) for w in worlds]


@router.get("/{user_id}/saved_games/", response_model=List[SavedGameDTO])
async def list_user_saved_games(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all saved games for a specific user.
    Users can only access their own saved games.
    """
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: user mismatch")
    
    games = db.query(SavedGame).filter(SavedGame.user_id == user_id).all()
    result = []
    for game in games:
        history_count = db.query(StoryHistory).filter(StoryHistory.saved_game_id == game.id).count()
        world = db.query(World).filter(World.id == game.world_id).first()
        rating = db.query(GameRating).filter(GameRating.id == game.rating_id).first()
        
        dto = SavedGameDTO(
            id=game.id,
            user_id=game.user_id,
            world_id=game.world_id,
            rating_id=game.rating_id,
            player_name=game.player_name,
            player_gender=game.player_gender,
            history_count=history_count,
            world_name=world.name if world else "",
            world_tokens=world.world_tokens if world else "",
            world_preface=world.preface if world else "",
            rating_name=rating.name if rating else "",
            story_splitter=f"# Continue {rating.ai_prompt} after the player action." if rating else "###",
            history=[],  # Empty list for summary
            tokenized_history=[],  # Empty list for summary
            deep_history=[],  # Empty list for summary
            created_at=game.created_at,
            updated_at=game.updated_at
        )
        result.append(dto)
    return result
