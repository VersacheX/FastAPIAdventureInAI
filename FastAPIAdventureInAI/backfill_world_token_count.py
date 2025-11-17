"""
Backfill script to populate token_count for existing worlds in the database.
Run this after migration to ensure all worlds have token_count set.
"""
import os
from dotenv import load_dotenv
load_dotenv()
from config import DATABASE_URL
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import World
from token_utils import count_tokens_batch

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

worlds = session.query(World).all()
for world in worlds:
    combined_text = f"{world.name} {world.preface} {world.world_tokens}"
    token_count = count_tokens_batch([combined_text])[0]
    world.token_count = token_count
    print(f"World {world.id} ({world.name}): token_count set to {token_count}")
session.commit()
print("Backfill complete.")
