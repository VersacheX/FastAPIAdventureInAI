from typing import List
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from business.dtos import WorldDTO
from business.models import User, World
from business.converters import world_to_dto
from aiadventureinpythonconstants import MAX_WORLD_TOKENS # THIS NEEDS TO BE REMOVED OR WE NEED TO DO IT MORE
from api.services.memory_service import ai_count_tokens_batch
from api.ai_client_requests import ai_count_tokens_batch
from shared.helpers.ai_settings import get_setting
from shared.services.auth_service import get_current_user
from shared.services.orm_service import get_db

async def perform_list_worlds(db: Session = Depends(get_db)):
    """
    Get all worlds.
    No authentication required.
    """
    worlds = db.query(World).all()
    return [world_to_dto(w, calculate_tokens=False) for w in worlds]

async def perform_create_world(
    world_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new world for the authenticated user.
    Validates world name uniqueness and token count limits.
    """
    # Check if world name already exists
    existing = db.query(World).filter(World.name == world_data["name"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="World name already exists")
    
    # Validate token count
    combined_text = f"{world_data['name']} {world_data['world_tokens']}" # remove preface {world_data['preface']}
    token_count = ai_count_tokens_batch([combined_text])[0]
    max_world_tokens = get_setting('MAX_WORLD_TOKENS', db)
    if max_world_tokens is None:
        max_world_tokens = MAX_WORLD_TOKENS
    if token_count > max_world_tokens:
        raise HTTPException(
            status_code=400, 
            detail=f"World token count ({token_count}) exceeds maximum allowed ({max_world_tokens})"
        )
    
    new_world = World(
        user_id=current_user.id,
        name=world_data["name"],
        preface=world_data["preface"],
        world_tokens=world_data["world_tokens"],
        token_count=token_count
    )
    db.add(new_world)
    db.commit()
    db.refresh(new_world)
    return world_to_dto(new_world, calculate_tokens=False)

async def perform_update_world(
    world_id: int,
    world_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing world.
    Only the owner can update their world.
    """
    world = db.query(World).filter(World.id == world_id).first()
    if not world:
        raise HTTPException(status_code=404, detail="World not found")
    
    # Check ownership
    if world.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: you can only edit your own worlds")
    
    # Check if new name conflicts with another world
    if "name" in world_data and world_data["name"] != world.name:
        existing = db.query(World).filter(World.name == world_data["name"]).first()
        if existing:
            raise HTTPException(status_code=400, detail="World name already exists")
    
    # Build updated text for token validation
    updated_name = world_data.get("name", world.name)
    updated_preface = world_data.get("preface", world.preface)
    updated_world_tokens = world_data.get("world_tokens", world.world_tokens)
    combined_text = f"{updated_name} {updated_world_tokens}" #{updated_preface}
    token_count = ai_count_tokens_batch([combined_text])[0]
    max_world_tokens = get_setting('MAX_WORLD_TOKENS', db)
    if max_world_tokens is None:
        max_world_tokens = MAX_WORLD_TOKENS
    if token_count > max_world_tokens:
        raise HTTPException(
            status_code=400, 
            detail=f"World token count ({token_count}) exceeds maximum allowed ({max_world_tokens})"
        )
    
    # Update world fields
    world.name = updated_name
    world.preface = updated_preface
    world.world_tokens = updated_world_tokens
    world.token_count = token_count
    db.commit()
    db.refresh(world)
    return world_to_dto(world, calculate_tokens=False)


async def perform_delete_world(
    world_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a world.
    Only the owner can delete their world.
    """
    world = db.query(World).filter(World.id == world_id).first()
    if not world:
        raise HTTPException(status_code=404, detail="World not found")
    
    # Check ownership
    if world.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: you can only delete your own worlds")
    
    db.delete(world)
    db.commit()
    return None
