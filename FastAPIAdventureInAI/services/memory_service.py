"""
Memory management service for story history compression and token counting.
Centralizes token counting, text summarization, and memory compression logic.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
import requests
import jwt

from business.models import StoryHistory, TokenizedHistory, DeepMemory, SavedGame
from ai.ai_client_requests import ai_count_tokens, ai_summarize_chunk
from ai.ai_settings import get_setting
from config import SECRET_KEY, ALGORITHM, AI_SERVER_URL


def _get_auth_headers():
    """Generate auth headers for AI server requests"""
    # Use 'system' user for internal server-to-server calls
    token = jwt.encode({"sub": "system"}, SECRET_KEY, algorithm=ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a text string using the AI model's tokenizer.
    This function calls the AI server to get accurate token counts.
    """
    try:
        response = requests.post(
            f"{AI_SERVER_URL}/count_tokens/",
            json={"text": text},
            headers=_get_auth_headers(),
            timeout=5
        )
        response.raise_for_status()
        return response.json()["token_count"]
    except Exception as e:
        # Fallback to rough estimate: ~4 characters per token
        return len(text) // 4


def count_tokens_batch(texts: list[str]) -> list[int]:
    """
    Count tokens for multiple texts in a single request.
    Returns a list of token counts in the same order as input texts.
    """
    try:
        response = requests.post(
            f"{AI_SERVER_URL}/count_tokens_batch/",
            json={"texts": texts},
            headers=_get_auth_headers(),
            timeout=10
        )
        response.raise_for_status()
        return response.json()["token_counts"]
    except Exception as e:
        # Fallback to rough estimate
        return [len(text) // 4 for text in texts]


def calculate_token_count(text: str) -> int:
    """
    Calculate token count for a single text using batch tokenizer.
    
    Args:
        text: Text to count tokens for
        
    Returns:
        Number of tokens in the text
    """
    return count_tokens_batch([text])[0]


def update_text_with_token_count(text: str, db_object, text_field: str = "text") -> int:
    """
    Update a database object's token_count field based on text content.
    
    Args:
        text: The text to count tokens for
        db_object: Database model instance with token_count field
        text_field: Name of the text field (for display purposes)
        
    Returns:
        The calculated token count
    """
    token_count = calculate_token_count(text)
    db_object.token_count = token_count
    return token_count


def summarize_history_chunk(
    history_texts: List[str],
    max_tokens: int,
    previous_summary: Optional[str] = None,
    username: Optional[str] = None
) -> tuple[str, int]:
    """
    Summarize a chunk of history entries using AI.
    
    Args:
        history_texts: List of history entry texts to summarize
        max_tokens: Maximum tokens for the summary
        previous_summary: Previous chunk's summary for context
        username: Username for AI request tracking
        
    Returns:
        Tuple of (summary_text, token_count)
    """
    print("[summarize_history_chunk] Payload:", {
        "chunk": history_texts,
        "max_tokens": max_tokens,
        "previous_summary": previous_summary,
        "username": username
    })
    
    summary = ai_summarize_chunk(
        history_texts,
        max_tokens,
        previous_summary=previous_summary,
        username=username
    )
    token_count = calculate_token_count(summary)
    return summary, token_count


def compress_to_deep_memory(
    summaries: List[str],
    max_tokens: int,
    username: Optional[str] = None
) -> tuple[str, int]:
    """
    Ultra-compress multiple summaries into deep memory format.
    
    Args:
        summaries: List of summary texts to compress
        max_tokens: Maximum tokens for the deep memory
        username: Username for AI request tracking
        
    Returns:
        Tuple of (deep_summary, token_count)
    """
    prompt = (
        "Compress these story summaries into a single ultra-concise deep memory.\n"
        "Extract ONLY the most critical information:\n"
        "  - Major plot arcs and their resolutions\n"
        "  - Significant character introductions and relationship shifts\n"
        "  - World-changing events or discoveries\n"
        "  - Ongoing missions or tasks\n"
        "Remove ALL minor details, scene descriptions, and redundant information.\n"
        "# Summaries to Compress:\n\n"
        + "\n\n---\n\n".join(summaries)
    )
    
    print("[compress_to_deep_memory] Payload:", {
        "chunk": [prompt],
        "max_tokens": max_tokens,
        "previous_summary": None,
        "username": username
    })

    deep_summary = ai_summarize_chunk(
        [prompt],
        max_tokens=max_tokens,
        previous_summary=None,
        username=username
    )

    token_count = calculate_token_count(deep_summary)
    return deep_summary, token_count


def ensure_history_token_counts(saved_game_id: int, db: Session) -> None:
    """
    Ensure all history entries for a game have token counts calculated.
    
    Args:
        saved_game_id: ID of the saved game
        db: Database session
    """
    entries_needing_counts = db.query(StoryHistory).filter(
        StoryHistory.saved_game_id == saved_game_id,
        StoryHistory.token_count == None
    ).all()
    
    if entries_needing_counts:
        texts = [entry.text for entry in entries_needing_counts]
        token_counts = count_tokens_batch(texts)
        for entry, count in zip(entries_needing_counts, token_counts):
            entry.token_count = count
        db.commit()


def get_active_tokenized_chunks(
    saved_game_id: int,
    db: Session,
    max_chunks: Optional[int] = None
) -> List[TokenizedHistory]:
    """
    Get active (non-compressed) tokenized chunks for a game.
    
    Args:
        saved_game_id: ID of the saved game
        db: Database session
        max_chunks: Maximum number of chunks to return (most recent first)
        
    Returns:
        List of active TokenizedHistory entries
    """
    query = db.query(TokenizedHistory).filter(
        TokenizedHistory.saved_game_id == saved_game_id,
        TokenizedHistory.is_tokenized == 0
    ).order_by(TokenizedHistory.end_index.desc())
    
    if max_chunks:
        query = query.limit(max_chunks)
    
    return query.all()


def get_untokenized_history(
    saved_game_id: int,
    db: Session
) -> List[StoryHistory]:
    """
    Get all untokenized history entries for a game.
    
    Args:
        saved_game_id: ID of the saved game
        db: Database session
        
    Returns:
        List of untokenized StoryHistory entries
    """
    return db.query(StoryHistory).filter(
        StoryHistory.saved_game_id == saved_game_id,
        StoryHistory.is_tokenized == 0
    ).order_by(StoryHistory.entry_index).all()


def calculate_active_memory_budget(
    saved_game_id: int,
    db: Session
) -> dict:
    """
    Calculate token budget breakdown for a game's active memory.
    
    Args:
        saved_game_id: ID of the saved game
        db: Database session
        
    Returns:
        Dict with token budget breakdown
    """
    MAX_TOKENIZED_HISTORY_BLOCK = get_setting('MAX_TOKENIZED_HISTORY_BLOCK', db)
    TOKENIZE_THRESHOLD = get_setting('TOKENIZE_THRESHOLD', db)
    
    # Get all history
    all_history = db.query(StoryHistory).filter(
        StoryHistory.saved_game_id == saved_game_id
    ).order_by(StoryHistory.id).all()
    
    # Get active tokenized chunks
    active_chunks = get_active_tokenized_chunks(
        saved_game_id,
        db,
        max_chunks=MAX_TOKENIZED_HISTORY_BLOCK
    )
    
    # Calculate untokenized history tokens
    untokenized = [h for h in all_history if not h.is_tokenized]
    untokenized.reverse()  # Most recent first
    
    active_history_tokens = 0
    active_history_count = 0
    for entry in untokenized:
        entry_tokens = entry.token_count or 0
        if active_history_tokens + entry_tokens <= TOKENIZE_THRESHOLD:
            active_history_tokens += entry_tokens
            active_history_count += 1
        else:
            break
    
    # Calculate active tokenized tokens
    active_tokenized_tokens = sum(chunk.token_count or 0 for chunk in active_chunks)
    
    # Total tokens
    total_tokens = sum(h.token_count or 0 for h in all_history)
    
    return {
        "active_tokens": active_tokenized_tokens + active_history_tokens,
        "total_tokens": total_tokens,
        "active_tokenized_chunks": len(active_chunks),
        "active_tokenized_tokens": active_tokenized_tokens,
        "active_history_entries": active_history_count,
        "active_history_tokens": active_history_tokens,
        "total_history_entries": len(all_history)
    }


def verify_game_ownership(
    game_id: int,
    user_id: int,
    db: Session
) -> SavedGame:
    """
    Verify that a user owns a saved game.
    
    Args:
        game_id: ID of the saved game
        user_id: ID of the user
        db: Database session
        
    Returns:
        The SavedGame if owned by user
        
    Raises:
        ValueError: If game not found or not owned by user
    """
    from fastapi import HTTPException
    
    game = db.query(SavedGame).filter(SavedGame.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Saved game not found")
    if game.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    
    return game
