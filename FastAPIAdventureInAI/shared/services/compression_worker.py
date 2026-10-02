"""
Background compression worker that processes jobs from the in-process queue.

This module registers a processor callback with the compression queue service.
It uses a fresh SQLAlchemy session per job and relies on memory_service helpers
for summarization/compression. Kept intentionally simple for development.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from shared.services.compression_queue_service import register_processor, enqueue_deep_compress
from shared.services.orm_service import SessionLocal
from api.services.memory_service import (
    ensure_history_token_counts,
    summarize_history_chunk,
    compress_to_deep_memory,
)
from shared.helpers.ai_settings import get_setting

# Import models locally to avoid import cycles
from business.models import (
    StoryHistory,
    TokenizedHistory,
    DeepMemory,
    CompressionJob,
)

logger = logging.getLogger(__name__)


def _process_job(job: dict) -> None:
    job_id = job.get("id")
    jtype = job.get("type")
    payload = job.get("payload") or {}
    saved_game_id: Optional[int] = payload.get("saved_game_id")
    username: Optional[str] = payload.get("username")

    db: Session = SessionLocal()
    job_row = None

    try:
        # persist job record
        job_row = CompressionJob(
            job_id=job_id,
            job_type=jtype,
            payload=json.dumps(payload),
            status="started",
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            saved_game_id=saved_game_id,
        )
        db.add(job_row)
        db.commit()

        if jtype == "tokenize_history":
            _handle_tokenize(db, saved_game_id, username)
        elif jtype == "deep_compress":
            _handle_deep_compress(db, saved_game_id, username)
        else:
            logger.warning("Unknown job type: %s", jtype)

        if job_row:
            job_row.status = "finished"
            job_row.finished_at = datetime.utcnow()
            db.commit()

    except Exception as e:
        logger.exception("Job failed: %s", job_id)
        if job_row:
            try:
                job_row.status = "failed"
                job_row.last_error = str(e)
                job_row.finished_at = datetime.utcnow()
                db.commit()
            except Exception:
                db.rollback()
        try:
            db.close()
        except Exception:
            pass


def _handle_tokenize(db: Session, saved_game_id: int, username: Optional[str]) -> None:
    # Ensure token counts exist for entries
    ensure_history_token_counts(saved_game_id, db)

    # Select entries that were marked sent_to_queue
    entries = (
        db.query(StoryHistory)
        .filter(
            StoryHistory.saved_game_id == saved_game_id,
            StoryHistory.is_tokenized == 0,
            StoryHistory.sent_to_queue == 1,
        )
        .order_by(StoryHistory.entry_index)
        .all()
    )

    if not entries:
        logger.info("No entries to tokenize for game %s", saved_game_id)
        return

    token_block_size = get_setting("TOKENIZED_HISTORY_BLOCK_SIZE", db)
    texts = [e.text for e in entries]

    # Create summary (may be trimmed to block size)
    new_summary, new_summary_token_count = summarize_history_chunk(
        texts, token_block_size, previous_summary=None, username=username
    )

    # Create new tokenized chunk
    new_tokenized = TokenizedHistory(
        saved_game_id=saved_game_id,
        start_index=entries[0].entry_index,
        end_index=entries[-1].entry_index,
        summary=new_summary,
        token_count=new_summary_token_count,
        history_references=",".join(str(e.id) for e in entries),
        created_at=datetime.utcnow(),
    )
    db.add(new_tokenized)

    # Mark entries tokenized and clear sent_to_queue
    for e in entries:
        e.is_tokenized = 1
        e.sent_to_queue = 0

    db.commit()

    # After creating tokenized chunk, enqueue deep compression check
    enqueue_deep_compress(saved_game_id, db=db, username=username)


def _handle_deep_compress(db: Session, saved_game_id: int, username: Optional[str]) -> None:
    # Find active tokenized chunks that were marked sent_to_queue
    chunks = (
        db.query(TokenizedHistory)
        .filter(
            TokenizedHistory.saved_game_id == saved_game_id,
            TokenizedHistory.is_tokenized == 0,
            TokenizedHistory.sent_to_queue == 1,
        )
        .order_by(TokenizedHistory.id.asc())
        .all()
    )

    if not chunks:
        logger.info("No tokenized chunks to compress for game %s", saved_game_id)
        return

    summaries = [c.summary for c in chunks]
    deep_tokens_limit = get_setting("DEEP_MEMORY_MAX_TOKENS", db)

    deep_summary, deep_token_count = compress_to_deep_memory(
        summaries, int(deep_tokens_limit), username=username
    )

    # Save or update DeepMemory row
    deep_memory = db.query(DeepMemory).filter(DeepMemory.saved_game_id == saved_game_id).first()

    if deep_memory:
        deep_memory.summary = deep_summary
        deep_memory.token_count = deep_token_count
        deep_memory.chunks_merged = (deep_memory.chunks_merged or 0) + len(chunks)
        deep_memory.last_merged_end_index = chunks[-1].end_index
        deep_memory.updated_at = datetime.utcnow()
    else:
        deep_memory = DeepMemory(
            saved_game_id=saved_game_id,
            summary=deep_summary,
            token_count=deep_token_count,
            chunks_merged=len(chunks),
            last_merged_end_index=chunks[-1].end_index,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(deep_memory)

    # Mark chunks as compressed and clear sent_to_queue
    for c in chunks:
        c.is_tokenized = 1
        c.sent_to_queue = 0

    db.commit()


# Register processor so worker thread in queue service will call this
register_processor(_process_job)
