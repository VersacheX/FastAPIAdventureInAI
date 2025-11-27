"""
Deep memory routes.
Handles ultra-compressed long-term story memory for saved games.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session


from business.schemas import DeepMemoryCreate, DeepMemoryUpdate
from business.models import User
from shared.services.orm_service import get_db
from shared.services.auth_service import get_current_user

from api.services.deep_memory_service import  (
    perform_create_deep_memory,
    perform_update_deep_memory
)

router = APIRouter(prefix="/deep_memory", tags=["deep memory"])


@router.post("/")
async def create_deep_memory(
    deep_memory: DeepMemoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_create_deep_memory(deep_memory, db, current_user)


@router.put("/{deep_memory_id}")
async def update_deep_memory(
    deep_memory_id: int,
    update: DeepMemoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_update_deep_memory(deep_memory_id, update, db, current_user)