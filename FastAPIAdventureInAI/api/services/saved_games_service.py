"""
Saved games routes.
Handles CRUD operations for saved games and related game statistics.
"""
from datetime import datetime, timezone
from typing import List
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from business.schemas import SavedGameCreate, SavedGameIdResponse
from business.dtos import SavedGameDTO, HistoryDTO, TokenizedHistoryDTO, DeepMemoryDTO
from business.models import User, SavedGame, StoryHistory, TokenizedHistory, DeepMemory
from business.converters import saved_game_to_dto
from shared.services.orm_service import get_db
from shared.services.auth_service import verify_game_ownership, get_current_user
from shared.helpers.ai_settings import get_setting
from api.services.memory_service import calculate_active_memory_budget
from api.services.history_service import check_and_tokenize_history

async def perform_get_saved_game(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a saved game with all related history, tokenized history, and deep memory.
    """
    game = db.query(SavedGame).filter(SavedGame.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Saved game not found")
    if game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    
    # Fetch related history, tokenized history, and deep history
    history = db.query(StoryHistory).filter(StoryHistory.saved_game_id == game_id).all()
    tokenized_history = db.query(TokenizedHistory).filter(TokenizedHistory.saved_game_id == game_id).all()
    deep_history = db.query(DeepMemory).filter(DeepMemory.saved_game_id == game_id).all()

    # Build and return the DTO, now including deep_history
    dto = saved_game_to_dto(game, history, tokenized_history, db)
    
    # Convert deep memory to DTOs and add to the DTO
    deep_history_dtos = [DeepMemoryDTO.model_validate(d) for d in deep_history]
    dto.deep_history = deep_history_dtos
    
    return dto

async def perform_list_tokenized_history(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get tokenized history for a saved game.
    Only returns active tokenized chunks (not compressed into deep memory).
    """
    game = db.query(SavedGame).filter(SavedGame.id == game_id).first()
    if not game or game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    
    # Only return active tokenized chunks (not compressed into deep memory)
    return db.query(TokenizedHistory).filter(
        TokenizedHistory.saved_game_id == game_id,
        TokenizedHistory.is_tokenized == 0
    ).all()

async def perform_get_deep_memory(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the ultra-compressed deep memory for ancient history (if it exists).
    """
    game = db.query(SavedGame).filter(SavedGame.id == game_id).first()
    if not game or game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    
    deep_memory = db.query(DeepMemory).filter(DeepMemory.saved_game_id == game_id).first()
    if not deep_memory:
        return {}  # Return empty object for consistency
    
    return {
        "id": deep_memory.id,
        "summary": deep_memory.summary,
        "token_count": deep_memory.token_count,
        "chunks_merged": deep_memory.chunks_merged,
        "last_merged_end_index": deep_memory.last_merged_end_index,
        "updated_at": deep_memory.updated_at
    }

async def perform_get_token_stats(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get token statistics for the game:
    - active_tokens: Tokens sent to AI (recent chunks + recent history)
    - total_tokens: All tokens in all history entries
    """
    verify_game_ownership(game_id, current_user.id, db)
    return calculate_active_memory_budget(game_id, db)

async def perform_update_saved_game(
    game_id: int,
    game_data: SavedGameCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a saved game's metadata."""
    game = verify_game_ownership(game_id, current_user.id, db)
    
    # Update fields
    game.world_id = game_data.world_id
    game.rating_id = game_data.rating_id
    game.player_name = game_data.player_name
    game.player_gender = game_data.player_gender
    game.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(game)
    return game

async def perform_create_saved_game(
    game_data: SavedGameCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new saved game.
    Can optionally include initial history and tokenized history.
    """
    if game_data.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: user mismatch")
    
    new_game = SavedGame(
        user_id=game_data.user_id,
        world_id=game_data.world_id,
        rating_id=game_data.rating_id,
        player_name=game_data.player_name,
        player_gender=game_data.player_gender,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(new_game)
    db.commit()
    db.refresh(new_game)

    # Save history entries if provided
    if game_data.history:
        for idx, entry in enumerate(game_data.history):
            new_history = StoryHistory(
                saved_game_id=new_game.id,
                entry_index=idx,
                text=entry.entry,
                created_at=datetime.now(timezone.utc)
            )
            db.add(new_history)

    # Save tokenized history blocks if provided
    if game_data.tokenized_history:
        for th in game_data.tokenized_history:
            new_th = TokenizedHistory(
                saved_game_id=new_game.id,
                start_index=th.start_index,
                end_index=th.end_index,
                summary=th.summary,
                created_at=datetime.now(timezone.utc)
            )
            db.add(new_th)

    db.commit()
    
    # Ensure initial history entries get token counts
    check_and_tokenize_history(new_game.id, db, username=current_user.username)
    
    return {"id": new_game.id}

async def perform_delete_saved_game(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a saved game and all related data."""
    game = verify_game_ownership(game_id, current_user.id, db)
    
    db.delete(game)
    db.commit()
    return {"detail": "Saved game deleted"}
