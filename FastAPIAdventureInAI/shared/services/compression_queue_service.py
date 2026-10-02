"""
Lightweight compression queue service.

This module provides a simple in-process queue and worker thread for enqueuing
compression-related jobs (tokenization and deep-memory compression). It is
intentionally decoupled from the history/tokenization implementation so you can
register a processor callback from `api.services.history_service` (or a
separate worker process) at runtime to avoid circular imports.

Usage pattern (recommended):
- At app startup register a processor function: `register_processor(my_processor)`.
 The processor should accept a single job dict and perform the work (DB
 operations, AI calls, etc.).
- Call `enqueue_tokenize_history(saved_game_id, db=session, username=username)`
 to mark rows as `sent_to_queue` and enqueue a job. If `db` is provided the
 function will mark relevant rows before enqueuing.

Note: This is a mock/simple queue for development and testing. For production
use a durable queue (Redis, RabbitMQ, Celery/RQ) and run workers in separate
processes.
"""
from __future__ import annotations

import threading
import queue
import uuid
import time
import logging
from typing import Callable, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Internal queue and worker state
_task_queue: queue.Queue = queue.Queue()
_processor: Optional[Callable[[dict], None]] = None
_worker_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


def _start_worker_if_needed() -> None:
    global _worker_thread
    if _worker_thread is None or not _worker_thread.is_alive():
        _stop_event.clear()
        _worker_thread = threading.Thread(
            target=_worker_loop, name="compression-queue-worker", daemon=True
        )
        _worker_thread.start()
        logger.info("Compression queue worker started")


def register_processor(processor: Callable[[dict], None]) -> None:
    """
    Register a processor callback that will be invoked for each job.

    The processor should accept a job dict and perform the necessary work
    (summarization, DB updates, deep compression, etc.). Registering the
    processor will start the background worker thread.
    """
    global _processor
    _processor = processor
    _start_worker_if_needed()


def stop_worker(timeout: Optional[float] = 1.0) -> None:
    """Stop the background worker."""
    _stop_event.set()
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        _worker_thread.join(timeout)


def _worker_loop() -> None:
    logger.debug("Worker loop running")
    while not _stop_event.is_set():
        try:
            job = _task_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        job_id = job.get("id")
        logger.info("Processing job %s type=%s", job_id, job.get("type"))

        try:
            if _processor:
                _processor(job)
            else:
                logger.warning("No processor registered for job %s; skipping", job_id)
        except Exception:
            logger.exception("Error while processing job %s", job_id)
            # In a real system you would record the failure, update DB job state,
            # and possibly requeue with backoff. For this mock we drop the job.
        finally:
            try:
                _task_queue.task_done()
            except Exception:
                pass

    logger.info("Worker loop exiting")


def enqueue_job(job_type: str, payload: dict) -> str:
    """
    Enqueue a generic job.

    Returns the job id.
    """
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "type": job_type,
        "payload": payload,
        "created_at": time.time(),
    }
    _task_queue.put(job)
    _start_worker_if_needed()
    logger.debug("Enqueued job %s type=%s", job_id, job_type)
    return job_id


def enqueue_tokenize_history(
    saved_game_id: int, db: Optional[Session] = None, username: Optional[str] = None
) -> str:
    """
    Enqueue a tokenize-history job.

    If `db` is provided, mark untokenized `StoryHistory` rows for the game as
    `sent_to_queue =1` to prevent duplicate enqueues.

    Returns generated job id.
    """
    # Optionally mark story entries as sent_to_queue to avoid duplicates
    if db is not None:
        # Import models lazily to avoid circular imports
        from business.models import StoryHistory

        rows = db.query(StoryHistory).filter(
            StoryHistory.saved_game_id == saved_game_id,
            StoryHistory.is_tokenized == 0,
            getattr(StoryHistory, "sent_to_queue", 0) == 0,
        ).all()

        if rows:
            for r in rows:
                setattr(r, "sent_to_queue", 1)
            try:
                db.commit()
            except Exception:
                db.rollback()
                logger.exception(
                    "Failed to mark story rows as sent_to_queue for game %s",
                    saved_game_id,
                )

    payload = {"saved_game_id": saved_game_id, "username": username}
    return enqueue_job("tokenize_history", payload)


def enqueue_deep_compress(
    saved_game_id: int, db: Optional[Session] = None, username: Optional[str] = None
) -> str:
    """
    Enqueue a deep-memory compression job.

    If `db` is provided, mark active `TokenizedHistory` rows for the game as
    `sent_to_queue =1` to avoid duplicate processing.
    """
    if db is not None:
        from business.models import TokenizedHistory

        rows = db.query(TokenizedHistory).filter(
            TokenizedHistory.saved_game_id == saved_game_id,
            TokenizedHistory.is_tokenized == 0,
            getattr(TokenizedHistory, "sent_to_queue", 0) == 0,
        ).all()

        if rows:
            for r in rows:
                setattr(r, "sent_to_queue", 1)
            try:
                db.commit()
            except Exception:
                db.rollback()
                logger.exception(
                    "Failed to mark tokenized rows as sent_to_queue for game %s",
                    saved_game_id,
                )

    payload = {"saved_game_id": saved_game_id, "username": username}
    return enqueue_job("deep_compress", payload)


def queue_size() -> int:
    return _task_queue.qsize()


# Expose a simple API for inspecting and clearing the queue (useful for tests)
def clear_queue() -> None:
    try:
        while True:
            _task_queue.get_nowait()
            _task_queue.task_done()
    except queue.Empty:
        pass


# Start a minimal worker when module is imported to keep dev experience simple.
# In production you should run dedicated worker processes and not rely on this.
_start_worker_if_needed()