"""
Game ratings routes.
Handles listing available content ratings for games.
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dependencies import get_db
from business.dtos import GameRatingDTO
from business.models import GameRating

router = APIRouter(prefix="/game_ratings", tags=["game ratings"])


@router.get("/", response_model=List[GameRatingDTO])
async def list_game_ratings(db: Session = Depends(get_db)):
    """
    Get all available game content ratings.
    No authentication required.
    """
    return db.query(GameRating).all()
