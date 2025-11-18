"""
Story history routes.
Handles CRUD operations for story history with automatic tokenization and compression.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from dependencies import get_db, get_current_user
from business.schemas import HistoryEntryIn
from business.dtos import HistoryDTO
from business.models import User, StoryHistory, TokenizedHistory, DeepMemory
from business.converters import history_to_dto
from ai.ai_settings import get_setting, get_memory_limits
from services.memory_service import (
    update_text_with_token_count,
    verify_game_ownership,
    summarize_history_chunk,
    compress_to_deep_memory,
    ensure_history_token_counts
)

router = APIRouter(prefix="/history", tags=["history"])


@router.post("/", response_model=HistoryDTO, status_code=201)
async def create_history_entry(
    history_data: HistoryEntryIn,
    saved_game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new history entry and trigger tokenization check.
    Auto-compresses history into tokenized chunks when threshold is exceeded.
    """
    game = verify_game_ownership(saved_game_id, current_user.id, db)
    
    max_entry_index = db.query(func.max(StoryHistory.entry_index)).filter(
        StoryHistory.saved_game_id == saved_game_id
    ).scalar()
    next_entry_index = (max_entry_index or -1) + 1
    
    new_history = StoryHistory(
        saved_game_id=saved_game_id,
        entry_index=next_entry_index,
        text=history_data.entry,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_history)
    db.commit()
    db.refresh(new_history)
    
    # Update game timestamp
    game.updated_at = datetime.now(timezone.utc)
    db.commit()
    
    # Check if tokenization is needed
    check_and_tokenize_history(saved_game_id, db, username=current_user.username)
    
    return history_to_dto(new_history)


@router.delete("/{history_id}", response_model=dict)
async def delete_history_entry(
    history_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a history entry and clean up tokenized chunk references."""
    history_entry = db.query(StoryHistory).filter(StoryHistory.id == history_id).first()
    if not history_entry:
        raise HTTPException(status_code=404, detail="History entry not found")
    
    verify_game_ownership(history_entry.saved_game_id, current_user.id, db)
    
    # Check for tokenized chunks that reference this history entry
    tokenized_chunks = db.query(TokenizedHistory).filter(
        TokenizedHistory.saved_game_id == history_entry.saved_game_id
    ).all()
    
    for chunk in tokenized_chunks:
        if chunk.history_references:
            ref_ids = [int(id.strip()) for id in chunk.history_references.split(',')]
            if history_id in ref_ids:
                # Remove this ID from references
                ref_ids.remove(history_id)
                
                if not ref_ids:
                    # No more references - delete the tokenized chunk
                    db.delete(chunk)
                else:
                    # Update the references list
                    chunk.history_references = ','.join(str(id) for id in ref_ids)
    
    db.delete(history_entry)
    db.commit()
    return {"detail": "History entry deleted"}


@router.put("/{history_id}", response_model=HistoryDTO)
async def update_history_entry(
    history_id: int,
    update_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a history entry's text and recalculate token count."""
    history_entry = db.query(StoryHistory).filter(StoryHistory.id == history_id).first()
    if not history_entry:
        raise HTTPException(status_code=404, detail="History entry not found")
    
    verify_game_ownership(history_entry.saved_game_id, current_user.id, db)
    
    # Update the text field (model uses 'text', not 'entry')
    if "text" in update_data:
        history_entry.text = update_data["text"]
        # Recalculate token count for the modified entry
        update_text_with_token_count(history_entry.text, history_entry)
    
    db.commit()
    db.refresh(history_entry)
    return HistoryDTO.model_validate(history_entry)


# ============================================================================
# HELPER FUNCTIONS: Tokenization and Deep Memory Compression
# ============================================================================

def check_and_tokenize_history(saved_game_id: int, db: Session, username: str = None):
    """
    Token-based history compression system:
    - Calculate token counts for all history entries
    - Create tokenized chunks when untokenized entries exceed token limit
    - Mark history entries as tokenized and track references
    - Refine the most recent tokenized chunk when new tokens are added to it
    """
    limits = get_memory_limits(db)
    TOKENIZE_THRESHOLD = get_setting('TOKENIZE_THRESHOLD', db)  # 800 tokens triggers compression
    TOKENIZED_HISTORY_BLOCK_SIZE = get_setting('TOKENIZED_HISTORY_BLOCK_SIZE', db)  # 200 tokens per chunk
    
    # Get all history entries ordered by index
    all_history = db.query(StoryHistory).filter(
        StoryHistory.saved_game_id == saved_game_id
    ).order_by(StoryHistory.entry_index).all()
    
    if not all_history:
        return
    
    # Calculate token counts for entries that don't have them
    ensure_history_token_counts(saved_game_id, db)
    
    # Get untokenized entries
    untokenized = [h for h in all_history if not h.is_tokenized]
    
    if not untokenized:
        return
    
    # Calculate total tokens in untokenized entries
    total_untokenized_tokens = sum(h.token_count or 0 for h in untokenized)
    
    # Check if we should create a new tokenized chunk (when untokenized exceeds TOKENIZE_THRESHOLD)
    if total_untokenized_tokens >= TOKENIZE_THRESHOLD:
        # Get the most recent tokenized chunk for this game
        latest_tokenized = db.query(TokenizedHistory).filter(
            TokenizedHistory.saved_game_id == saved_game_id
        ).order_by(TokenizedHistory.end_index.desc()).first()
        
        # Check if we should merge with the latest chunk (if it's less than 90% full)
        should_merge = False
        chunk_entries = untokenized  # Always start with just the new untokenized entries
        
        if latest_tokenized and latest_tokenized.token_count:
            # Calculate if the latest chunk is less than 90% of target size
            utilization = latest_tokenized.token_count / TOKENIZED_HISTORY_BLOCK_SIZE
            if utilization < 0.9:
                should_merge = True
                # We'll use the existing summary as context, not re-summarize the old entries
        
        # Summarize the NEW entries only
        # Get previous chunk summary for context
        previous_summary = None
        if should_merge and latest_tokenized:
            # Use the existing chunk's summary as context for the new summary
            previous_summary = latest_tokenized.summary
        elif latest_tokenized:
            # When creating new chunk, use the latest existing chunk as context
            previous_summary = latest_tokenized.summary
        
        chunk_text = [e.text for e in chunk_entries]
        new_summary, new_summary_token_count = summarize_history_chunk(
            chunk_text,
            TOKENIZED_HISTORY_BLOCK_SIZE,
            previous_summary=previous_summary,
            username=username
        )
        
        # Create history references string
        if should_merge and latest_tokenized:
            # When merging, combine old summary with new summary
            if latest_tokenized.summary:
                # Append new summary to old summary
                combined_summary = f"{latest_tokenized.summary}\n{new_summary}"
                combined_token_count = latest_tokenized.token_count + new_summary_token_count
            else:
                combined_summary = new_summary
                combined_token_count = new_summary_token_count
            
            # Check if combined summary exceeds the block size limit
            if combined_token_count > TOKENIZED_HISTORY_BLOCK_SIZE:
                # Combined summary is too large - create a new chunk instead
                should_merge = False
                print(f"Combined summary would be {combined_token_count} tokens (limit: {TOKENIZED_HISTORY_BLOCK_SIZE}), creating new chunk instead")
                summary = new_summary
                summary_token_count = new_summary_token_count
                history_references = ','.join([str(e.id) for e in chunk_entries])
            else:
                # Combined summary fits - use it for the merge
                summary = combined_summary
                summary_token_count = combined_token_count
                
                # Include both old and new entry IDs
                if latest_tokenized.history_references:
                    old_ids = latest_tokenized.history_references.split(',')
                    new_ids = [str(e.id) for e in chunk_entries]
                    all_ids = old_ids + new_ids
                    history_references = ','.join(all_ids)
                else:
                    history_references = ','.join([str(e.id) for e in chunk_entries])
        else:
            # Not merging - use new summary as-is
            summary = new_summary
            summary_token_count = new_summary_token_count
            history_references = ','.join([str(e.id) for e in chunk_entries])
        
        if should_merge and latest_tokenized:
            # Update existing chunk with merged content
            latest_tokenized.summary = summary
            latest_tokenized.token_count = summary_token_count
            latest_tokenized.end_index = chunk_entries[-1].entry_index
            latest_tokenized.history_references = history_references
            print(f"Updated tokenized chunk (was {utilization*100:.1f}% full, merged with {len(untokenized)} new entries)")
        else:
            # Create new tokenized chunk
            new_tokenized = TokenizedHistory(
                saved_game_id=saved_game_id,
                start_index=chunk_entries[0].entry_index,
                end_index=chunk_entries[-1].entry_index,
                summary=summary,
                token_count=summary_token_count,
                history_references=history_references,
                created_at=datetime.now(timezone.utc)
            )
            db.add(new_tokenized)
            print(f"Created new tokenized chunk with {len(chunk_entries)} entries ({summary_token_count} tokens)")
        
        # Mark all chunk entries as tokenized
        for entry in chunk_entries:
            entry.is_tokenized = 1
        
        db.commit()
        
        # Check if we need to compress into deep memory
        compress_old_chunks_to_deep_memory(saved_game_id, db, username)


def compress_old_chunks_to_deep_memory(saved_game_id: int, db: Session, username: str = None):
    """
    When tokenized chunks exceed MAX_TOKENIZED_HISTORY_BLOCK, merge oldest chunks into deep memory.
    This keeps the tokenized history manageable while preserving ancient story context.
    """
    MAX_TOKENIZED_HISTORY_BLOCK = get_setting('MAX_TOKENIZED_HISTORY_BLOCK', db)
    DEEP_MEMORY_MAX_TOKENS = get_setting('DEEP_MEMORY_MAX_TOKENS', db)
    
    # Count current ACTIVE tokenized chunks (not yet compressed into deep memory)
    chunk_count = db.query(TokenizedHistory).filter(
        TokenizedHistory.saved_game_id == saved_game_id,
        TokenizedHistory.is_tokenized == 0
    ).count()
    
    if chunk_count <= MAX_TOKENIZED_HISTORY_BLOCK:
        return  # No compression needed
    
    # How many chunks to merge into deep memory
    chunks_to_compress = chunk_count - MAX_TOKENIZED_HISTORY_BLOCK + 2  # Compress extras + 2 more
    
    # Get oldest ACTIVE chunks to compress
    old_chunks = db.query(TokenizedHistory).filter(
        TokenizedHistory.saved_game_id == saved_game_id,
        TokenizedHistory.is_tokenized == 0
    ).order_by(TokenizedHistory.end_index.asc()).limit(chunks_to_compress).all()
    
    if not old_chunks:
        return
    
    print(f"\n{'='*80}")
    print(f"DEEP MEMORY COMPRESSION: {len(old_chunks)} chunks exceed limit")
    print(f"{'='*80}")
    print(f"Current tokenized chunks: {chunk_count}")
    print(f"Max allowed: {MAX_TOKENIZED_HISTORY_BLOCK}")
    print(f"Compressing {chunks_to_compress} oldest chunks into deep memory...")
    print(f"{'='*80}\n")
    
    # Get or create deep memory for this game
    deep_memory = db.query(DeepMemory).filter(
        DeepMemory.saved_game_id == saved_game_id
    ).first()
    
    # Combine old chunks with existing deep memory
    summaries_to_merge = []
    if deep_memory:
        summaries_to_merge.append(deep_memory.summary)
    
    for chunk in old_chunks:
        summaries_to_merge.append(chunk.summary)
    
    # Ultra-compress into deep memory
    deep_summary, deep_token_count = compress_to_deep_memory(
        summaries_to_merge,
        DEEP_MEMORY_MAX_TOKENS,
        username=username
    )
    
    if deep_memory:
        # Update existing deep memory
        deep_memory.summary = deep_summary
        deep_memory.token_count = deep_token_count
        deep_memory.chunks_merged += len(old_chunks)
        deep_memory.last_merged_end_index = old_chunks[-1].end_index
        deep_memory.updated_at = datetime.now(timezone.utc)
        print(f"Updated deep memory: {deep_memory.chunks_merged} total chunks compressed")
    else:
        # Create new deep memory
        deep_memory = DeepMemory(
            saved_game_id=saved_game_id,
            summary=deep_summary,
            token_count=deep_token_count,
            chunks_merged=len(old_chunks),
            last_merged_end_index=old_chunks[-1].end_index,
            created_at=datetime.now(timezone.utc)
        )
        db.add(deep_memory)
        print(f"Created deep memory: {len(old_chunks)} chunks compressed")
    
    # Mark the compressed tokenized chunks as tokenized (compressed into deep memory)
    for chunk in old_chunks:
        chunk.is_tokenized = 1
    
    db.commit()
    
    # Calculate and display total token budget
    TOKENIZE_THRESHOLD = get_setting('TOKENIZE_THRESHOLD', db)
    remaining_chunks = chunk_count - chunks_to_compress
    total_memory_tokens = deep_token_count + (remaining_chunks * get_setting('TOKENIZED_HISTORY_BLOCK_SIZE', db)) + TOKENIZE_THRESHOLD
    
    print(f"✓ Deep memory compression complete!")
    print(f"  - Deep Memory: {deep_token_count} tokens")
    print(f"  - Tokenized Chunks ({remaining_chunks}): {remaining_chunks * get_setting('TOKENIZED_HISTORY_BLOCK_SIZE', db)} tokens (approx)")
    print(f"  - Recent History: up to {TOKENIZE_THRESHOLD} tokens")
    print(f"  - TOTAL MEMORY BUDGET: ~{total_memory_tokens} tokens")
    print(f"{'='*80}\n")
