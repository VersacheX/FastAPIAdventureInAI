"""
Deep memory routes.
Handles ultra-compressed long-term story memory for saved games.
"""
from datetime import datetime
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session


from business.schemas import DeepMemoryCreate, DeepMemoryUpdate
from business.models import User, DeepMemory
from api.services.memory_service import ai_calculate_token_count
from shared.services.orm_service import get_db
from shared.services.auth_service import verify_game_ownership, get_current_user

async def perform_create_deep_memory(
    deep_memory: DeepMemoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new deep memory entry for a saved game.
    Deep memory stores ultra-compressed summaries of ancient story events.
    """
    verify_game_ownership(deep_memory.saved_game_id, current_user.id, db)

    # Only allow one DeepMemory per saved_game_id
    existing = db.query(DeepMemory).filter(DeepMemory.saved_game_id == deep_memory.saved_game_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Deep memory already exists for this saved game")

    token_count = ai_calculate_token_count(deep_memory.summary)
    new_deep_memory = DeepMemory(
        saved_game_id=deep_memory.saved_game_id,
        summary=deep_memory.summary,
        token_count=token_count,
        chunks_merged=0,
        last_merged_end_index=0,
        updated_at=datetime.utcnow()
    )
    db.add(new_deep_memory)
    db.commit()
    db.refresh(new_deep_memory)
    return {
        "id": new_deep_memory.id,
        "summary": new_deep_memory.summary,
        "token_count": new_deep_memory.token_count,
        "chunks_merged": new_deep_memory.chunks_merged,
        "last_merged_end_index": new_deep_memory.last_merged_end_index,
        "updated_at": new_deep_memory.updated_at
    }

async def perform_update_deep_memory(
    deep_memory_id: int,
    update: DeepMemoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update the deep memory summary (for manual editing).
    Automatically recalculates token count.
    """
    deep_memory = db.query(DeepMemory).filter(DeepMemory.id == deep_memory_id).first()
    if not deep_memory:
        raise HTTPException(status_code=404, detail="Deep memory not found")

    # Verify ownership via saved_game
    verify_game_ownership(deep_memory.saved_game_id, current_user.id, db)

    # Update summary
    deep_memory.summary = update.summary

    # Recalculate token count
    deep_memory.token_count = ai_calculate_token_count(update.summary)

    # Update timestamp
    deep_memory.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(deep_memory)

    return {
        "id": deep_memory.id,
        "summary": deep_memory.summary,
        "token_count": deep_memory.token_count,
        "chunks_merged": deep_memory.chunks_merged,
        "last_merged_end_index": deep_memory.last_merged_end_index,
        "updated_at": deep_memory.updated_at
    }
