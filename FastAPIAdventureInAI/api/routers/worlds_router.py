"""
World routes.
Handles world CRUD operations (create, read, update, delete).
"""
from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy.orm import Session

from business.dtos import WorldDTO
from business.models import User
from shared.services.auth_service import get_current_user
from shared.services.orm_service import get_db

from api.services.worlds_service import (
    perform_list_worlds,
    perform_create_world,
    perform_update_world,
    perform_delete_world
)

router = APIRouter(prefix="/worlds", tags=["worlds"])


@router.get("/", response_model=List[WorldDTO])
async def list_worlds(db: Session = Depends(get_db)):
    return await perform_list_worlds(db)

@router.post("/", response_model=WorldDTO, status_code=201)
async def create_world(
    world_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_create_world(world_data, db, current_user)

@router.patch("/{world_id}", response_model=WorldDTO)
async def update_world(
    world_id: int,
    world_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_update_world(world_id, world_data, db, current_user)

@router.delete("/{world_id}", status_code=204)
async def delete_world(
    world_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await perform_delete_world(world_id, db, current_user)