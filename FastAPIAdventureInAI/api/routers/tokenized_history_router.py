"""
Tokenized history routes.
Handles compressed chunks of story history for memory efficiency.
"""
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session


from business.schemas import TokenizedHistoryIn
from business.dtos import TokenizedHistoryDTO
from business.models import User, TokenizedHistory
from business.converters import tokenized_history_to_dto
from api.services.memory_service import update_text_with_token_count
from shared.services.orm_service import get_db
from shared.services.auth_service import verify_game_ownership, get_current_user

router = APIRouter(prefix="/tokenized_history", tags=["tokenized history"])


@router.post("/", response_model=TokenizedHistoryDTO, status_code=201)
async def create_tokenized_history_entry(
    th_data: TokenizedHistoryIn,
    saved_game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new tokenized history chunk.
    Tokenized history compresses groups of story entries into summaries.
    """
    verify_game_ownership(saved_game_id, current_user.id, db)
    
    new_th = TokenizedHistory(
        saved_game_id=saved_game_id,
        start_index=th_data.start_index,
        end_index=th_data.end_index,
        summary=th_data.summary,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_th)
    db.commit()
    db.refresh(new_th)
    return tokenized_history_to_dto(new_th)


@router.put("/{tokenized_id}", response_model=TokenizedHistoryDTO)
async def update_tokenized_history_entry(
    tokenized_id: int,
    update_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a tokenized history entry.
    Recalculates token count when summary is modified.
    """
    tokenized_entry = db.query(TokenizedHistory).filter(TokenizedHistory.id == tokenized_id).first()
    if not tokenized_entry:
        raise HTTPException(status_code=404, detail="Tokenized history entry not found")
    
    verify_game_ownership(tokenized_entry.saved_game_id, current_user.id, db)
    
    # Update allowed fields
    if "summary" in update_data:
        tokenized_entry.summary = update_data["summary"]
        # Recalculate token count for the modified summary
        update_text_with_token_count(tokenized_entry.summary, tokenized_entry)
    if "start_index" in update_data:
        tokenized_entry.start_index = update_data["start_index"]
    if "end_index" in update_data:
        tokenized_entry.end_index = update_data["end_index"]
    
    db.commit()
    db.refresh(tokenized_entry)
    return tokenized_history_to_dto(tokenized_entry)


@router.delete("/{tokenized_id}")
async def delete_tokenized_history_entry(
    tokenized_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a tokenized history chunk."""
    tokenized_entry = db.query(TokenizedHistory).filter(TokenizedHistory.id == tokenized_id).first()
    if not tokenized_entry:
        raise HTTPException(status_code=404, detail="Tokenized history entry not found")
    
    verify_game_ownership(tokenized_entry.saved_game_id, current_user.id, db)
    
    db.delete(tokenized_entry)
    db.commit()
    return {"detail": "Tokenized history entry deleted"}
