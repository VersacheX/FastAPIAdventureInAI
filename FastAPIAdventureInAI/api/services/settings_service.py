"""
AI directive settings service (data server side).

Exposes the DB-backed AI settings so the AI server (which cannot reach SQL
Server directly, e.g. running in WSL) can fetch them over HTTP, and lets the
dev app manage them.
"""
import logging

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from business.models import AIDirectiveSettings
from business.dtos import AIDirectiveSettingsDTO
from shared.services.orm_service import get_db
from shared.helpers.ai_settings import (
    _get_ai_settings_from_db,
    invalidate_settings_cache,
)


logger = logging.getLogger(__name__)


async def perform_resolve_settings(
    settings_id: int = None,
    user_id: int = None,
    db: Session = Depends(get_db),
):
    """Return the fully-built settings dict (same shape get_ai_settings yields).

    This is what the AI server consumes. No auth so the AI server can fetch it
    freely on the trusted LAN; it contains no secrets.

    Use the strict DB read (not get_ai_settings) so a database outage surfaces as
    a 500 instead of silently returning hardcoded constants. If this endpoint
    returned 200 with constants during an outage, the AI server would treat them
    as a successful remote value and overwrite its stale last-known-good cache,
    bypassing its own _remote_fallback_settings stale-cache protection.
    """
    try:
        return _get_ai_settings_from_db(
            db=db, settings_id=settings_id, user_id=user_id, force_reload=True
        )
    except Exception as e:
        # This endpoint is unauthenticated, so never leak raw SQLAlchemy/ODBC
        # error text (server, driver, database, or query details). Log it
        # server-side and return a generic 503 instead.
        logger.exception("[settings] /settings/resolve DB read failed")
        raise HTTPException(
            status_code=503,
            detail="Settings database unavailable",
        )


async def perform_get_settings(settings_id: int, db: Session = Depends(get_db)):
    """Return the raw settings row for the dev app to edit."""
    settings = db.query(AIDirectiveSettings).filter_by(id=settings_id).first()
    if not settings:
        raise HTTPException(status_code=404, detail=f"Settings id {settings_id} not found")
    return settings


async def perform_list_settings(db: Session = Depends(get_db)):
    """List all settings rows for the dev app."""
    return db.query(AIDirectiveSettings).all()


async def perform_update_settings(settings_id: int, updates: dict, db: Session = Depends(get_db)):
    """Partially update a settings row from the dev app, then return it."""
    settings = db.query(AIDirectiveSettings).filter_by(id=settings_id).first()
    if not settings:
        raise HTTPException(status_code=404, detail=f"Settings id {settings_id} not found")

    allowed = {c.name for c in AIDirectiveSettings.__table__.columns if c.name != "id"}
    for key, value in updates.items():
        if key in allowed and value is not None:
            setattr(settings, key, value)

    # Keep the computed safe_prompt_limit consistent if the inputs changed.
    settings.safe_prompt_limit = settings.max_tokens - settings.reserved_for_generation

    db.commit()
    db.refresh(settings)

    # The row changed, so any cached settings are now stale. Clear the cache so
    # the next read (including the AI server's remote /settings/resolve fetch)
    # rebuilds from the updated row.
    invalidate_settings_cache()

    return settings
