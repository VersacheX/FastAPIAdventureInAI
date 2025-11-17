from dtos import UserDTO, WorldDTO, GameRatingDTO, HistoryDTO, TokenizedHistoryDTO, SavedGameDTO
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import uuid
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from argon2 import PasswordHasher, exceptions

from converters import (
    user_to_dto,
    world_to_dto,
    game_rating_to_dto,
    history_to_dto,
    tokenized_history_to_dto,
    saved_game_to_dto
)
from models import Base, User, World, GameRating, SavedGame, TokenizedHistory, StoryHistory, DeepMemory, Session as SessionModel

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import configuration from environment
from config import DATABASE_URL, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, CORS_ORIGINS
from aiadventureinpythonconstants import MAX_WORLD_TOKENS

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

app = FastAPI()

# CORS middleware
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Password hashing setup
ph = PasswordHasher()

# JWT setup (configuration loaded from environment)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    try:
        return ph.verify(hashed_password, plain_password)
    except exceptions.VerifyMismatchError:
        return False
    except exceptions.VerificationError:
        return False

def get_password_hash(password):
    return ph.hash(password)

def create_access_token(data: dict, expires_delta=None):
    from datetime import datetime, timedelta
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user

# Pydantic schemas
class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    password: str

class UserRegister(BaseModel):
    username: str
    email: Optional[str] = None
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class HistoryIn(BaseModel):
    entry: str

class TokenizedHistoryIn(BaseModel):
    start_index: int
    end_index: int
    summary: str

class SavedGameCreate(BaseModel):
    user_id: int
    world_id: int
    rating_id: int
    player_name: str
    player_gender: str
    history: Optional[List[HistoryIn]] = None
    tokenized_history: Optional[List[TokenizedHistoryIn]] = None

class SavedGameIdResponse(BaseModel):
    id: int

class DeepMemoryCreate(BaseModel):
    saved_game_id: int
    summary: str = ""

# Dependency to get current user from token
from fastapi import status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_username(db, username)
    if user is None:
        raise credentials_exception
    return user

# User endpoints
@app.post("/users/", response_model=UserDTO)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(username=user.username, email=user.email)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/users/{user_id}", response_model=UserDTO)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user_to_dto(user)  # Use converter

@app.get("/users/by_username/{username}", response_model=UserDTO)
def get_user_by_username_endpoint(
    username: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# Worlds and Ratings
@app.get("/worlds/", response_model=List[WorldDTO])
def list_worlds(db: Session = Depends(get_db)):
    worlds = db.query(World).all()
    return [world_to_dto(w, calculate_tokens=False) for w in worlds]

@app.get("/users/me/worlds/", response_model=List[WorldDTO])
def list_my_worlds(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all worlds belonging to the current user."""
    worlds = db.query(World).filter(World.user_id == current_user.id).all()
    return [world_to_dto(w, calculate_tokens=True) for w in worlds]

@app.post("/worlds/", response_model=WorldDTO, status_code=201)
def create_world(
    world_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new world for the current user."""
    from token_utils import count_tokens_batch
    from ai_settings import get_setting
    # Check if world name already exists
    existing = db.query(World).filter(World.name == world_data["name"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="World name already exists")
    # Validate token count
    combined_text = f"{world_data['name']} {world_data['preface']} {world_data['world_tokens']}"
    token_count = count_tokens_batch([combined_text])[0]
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
        token_count=token_count  # Store token count
    )
    db.add(new_world)
    db.commit()
    db.refresh(new_world)
    return world_to_dto(new_world, calculate_tokens=False)

@app.patch("/worlds/{world_id}", response_model=WorldDTO)
def update_world(
    world_id: int,
    world_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an existing world. Only the owner can update."""
    from token_utils import count_tokens_batch
    from ai_settings import get_setting
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
    combined_text = f"{updated_name} {updated_preface} {updated_world_tokens}"
    token_count = count_tokens_batch([combined_text])[0]
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
    world.token_count = token_count  # Store token count
    db.commit()
    db.refresh(world)
    return world_to_dto(world, calculate_tokens=False)

@app.delete("/worlds/{world_id}", status_code=204)
def delete_world(
    world_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a world. Only the owner can delete."""
    world = db.query(World).filter(World.id == world_id).first()
    if not world:
        raise HTTPException(status_code=404, detail="World not found")
    # Check ownership
    if world.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: you can only delete your own worlds")
    db.delete(world)
    db.commit()
    return None

@app.get("/game_ratings/", response_model=List[GameRatingDTO])
def list_game_ratings(db: Session = Depends(get_db)):
    return db.query(GameRating).all()

# Saved Games
@app.get("/saved_games/{game_id}", response_model=SavedGameDTO)
def get_saved_game(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    game = db.query(SavedGame).filter(SavedGame.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Saved game not found")
    if game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    
    # Fetch related history and tokenized history
    history = db.query(StoryHistory).filter(StoryHistory.saved_game_id == game_id).all()
    tokenized_history = db.query(TokenizedHistory).filter(TokenizedHistory.saved_game_id == game_id).all()
    
    # Convert to DTOs
    history_dtos = [HistoryDTO.model_validate(h) for h in history]
    tokenized_history_dtos = [TokenizedHistoryDTO.model_validate(th) for th in tokenized_history]
    
    # Build and return the DTO
    return saved_game_to_dto(game, history, tokenized_history, db)

@app.get("/users/{user_id}/saved_games/", response_model=List[SavedGameDTO])
def list_user_saved_games(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: user mismatch")
    games = db.query(SavedGame).filter(SavedGame.user_id == user_id).all()
    result = []
    for game in games:
        history_count = db.query(StoryHistory).filter(StoryHistory.saved_game_id == game.id).count()
        world = db.query(World).filter(World.id == game.world_id).first()
        rating = db.query(GameRating).filter(GameRating.id == game.rating_id).first()
        dto = SavedGameDTO(
            id=game.id,
            user_id=game.user_id,
            world_id=game.world_id,
            rating_id=game.rating_id,
            player_name=game.player_name,
            player_gender=game.player_gender,
            history_count=history_count,
            world_name=world.name if world else "",
            world_tokens=world.world_tokens if world else "",
            world_preface=world.preface if world else "",
            rating_name=rating.name if rating else "",
            story_splitter=f"# Continue {rating.ai_prompt} after the player action." if rating else "###",
            history=[],  # Empty list for summary
            tokenized_history=None,  # None for summary
            created_at=game.created_at,
            updated_at=game.updated_at
        )
        result.append(dto)
    return result

# Tokenized History
@app.get("/saved_games/{game_id}/tokenized_history/", response_model=List[TokenizedHistoryDTO])
def list_tokenized_history(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    game = db.query(SavedGame).filter(SavedGame.id == game_id).first()
    if not game or game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    # Only return active tokenized chunks (not compressed into deep memory)
    return db.query(TokenizedHistory).filter(
        TokenizedHistory.saved_game_id == game_id,
        TokenizedHistory.is_tokenized == 0
    ).all()


# Deep Memory Endpoints
class DeepMemoryUpdate(BaseModel):
    summary: str

class DeepMemoryCreate(BaseModel):
    saved_game_id: int
    summary: str = ""

@app.get("/saved_games/{game_id}/deep_memory/")
def get_deep_memory(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the ultra-compressed deep memory for ancient history (if it exists).
    """
    game = db.query(SavedGame).filter(SavedGame.id == game_id).first()
    if not game or game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    deep_memory = db.query(DeepMemory).filter(DeepMemory.saved_game_id == game_id).first()
    if not deep_memory:
        return {}  # Return empty object for consistency
    return {
        "id": deep_memory.id,
        "summary": deep_memory.summary,
        "token_count": deep_memory.token_count,
        "chunks_merged": deep_memory.chunks_merged,
        "last_merged_end_index": deep_memory.last_merged_end_index,
        "updated_at": deep_memory.updated_at
    }

@app.post("/deep_memory/")
def create_deep_memory(
    deep_memory: DeepMemoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new DeepMemory entry for a saved game.
    """
    from ai_client_requests import ai_count_tokens

    game = db.query(SavedGame).filter(SavedGame.id == deep_memory.saved_game_id).first()
    if not game or game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")

    # Only allow one DeepMemory per saved_game_id
    existing = db.query(DeepMemory).filter(DeepMemory.saved_game_id == deep_memory.saved_game_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Deep memory already exists for this saved game")

    token_count = ai_count_tokens(deep_memory.summary)
    new_deep_memory = DeepMemory(
        saved_game_id=deep_memory.saved_game_id,
        summary=deep_memory.summary,
        token_count=token_count,
        chunks_merged=0,
        last_merged_end_index=0,
        updated_at=datetime.utcnow()
    )
    db.add(new_deep_memory)
    db.commit()
    db.refresh(new_deep_memory)
    return {
        "id": new_deep_memory.id,
        "summary": new_deep_memory.summary,
        "token_count": new_deep_memory.token_count,
        "chunks_merged": new_deep_memory.chunks_merged,
        "last_merged_end_index": new_deep_memory.last_merged_end_index,
        "updated_at": new_deep_memory.updated_at
    }

@app.put("/deep_memory/{deep_memory_id}")
def update_deep_memory(
    deep_memory_id: int,
    update: DeepMemoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update the deep memory summary (for manual editing).
    Recalculates token count automatically.
    """
    from ai_client_requests import ai_count_tokens

    deep_memory = db.query(DeepMemory).filter(DeepMemory.id == deep_memory_id).first()
    if not deep_memory:
        raise HTTPException(status_code=404, detail="Deep memory not found")

    # Verify ownership via saved_game
    game = db.query(SavedGame).filter(SavedGame.id == deep_memory.saved_game_id).first()
    if not game or game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your deep memory")

    # Update summary
    deep_memory.summary = update.summary

    # Recalculate token count
    deep_memory.token_count = ai_count_tokens(update.summary)

    # Update timestamp
    deep_memory.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(deep_memory)

    return {
        "id": deep_memory.id,
        "summary": deep_memory.summary,
        "token_count": deep_memory.token_count,
        "chunks_merged": deep_memory.chunks_merged,
        "last_merged_end_index": deep_memory.last_merged_end_index,
        "updated_at": deep_memory.updated_at
    }

@app.get("/saved_games/{game_id}/token_stats")
def get_token_stats(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns token statistics for the game:
    - active_tokens: Tokens sent to AI (recent MAX_TOKENIZED_HISTORY_BLOCK chunks + up to TOKENIZE_THRESHOLD tokens of recent history)
    - total_tokens: All tokens in all history entries
    """
    from ai_settings import get_setting
    
    game = db.query(SavedGame).filter(SavedGame.id == game_id).first()
    if not game or game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    
    MAX_TOKENIZED_HISTORY_BLOCK = get_setting('MAX_TOKENIZED_HISTORY_BLOCK', db)
    TOKENIZE_THRESHOLD = get_setting('TOKENIZE_THRESHOLD', db)
    
    # Get all history
    all_history = db.query(StoryHistory).filter(
        StoryHistory.saved_game_id == game_id
    ).order_by(StoryHistory.id).all()
    
    # Get tokenized chunks ordered by most recent
    tokenized_chunks = db.query(TokenizedHistory).filter(
        TokenizedHistory.saved_game_id == game_id
    ).order_by(TokenizedHistory.end_index.desc()).limit(MAX_TOKENIZED_HISTORY_BLOCK).all()
    
    # Calculate active history tokens (most recent untokenized entries up to TOKENIZE_THRESHOLD)
    untokenized_history = [h for h in all_history if not h.is_tokenized]
    untokenized_history.reverse()  # Most recent first
    
    active_history_tokens = 0
    active_history_count = 0
    for entry in untokenized_history:
        entry_tokens = entry.token_count or 0
        if active_history_tokens + entry_tokens <= TOKENIZE_THRESHOLD:
            active_history_tokens += entry_tokens
            active_history_count += 1
        else:
            break
    
    # Calculate active tokenized tokens
    active_tokenized_tokens = sum(chunk.token_count or 0 for chunk in tokenized_chunks)
    
    # Total active tokens sent to AI
    active_tokens = active_tokenized_tokens + active_history_tokens
    
    # Calculate total tokens
    total_tokens = sum(h.token_count or 0 for h in all_history)
    
    return {
        "active_tokens": active_tokens,
        "total_tokens": total_tokens,
        "active_tokenized_chunks": len(tokenized_chunks),
        "active_history_entries": active_history_count,
        "total_history_entries": len(all_history)
    }

# Register endpoint (with password hashing)
@app.post("/register/", response_model=UserDTO)
def register(user: UserRegister, db: Session = Depends(get_db)):
    if get_user_by_username(db, user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(user.password)
    db_user = User(username=user.username, email=user.email, password_hash=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Login endpoint (returns JWT token)
@app.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username})

    # Persist the session token in the database with an expiry timestamp
    try:
        expires_at = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        db_session = SessionModel(
            user_id=user.id,
            token=access_token,
            expires_at=expires_at,
            last_activity=datetime.utcnow()
        )
        db.add(db_session)
        db.commit()
    except Exception:
        # If DB write fails, do not block authentication; just log/continue
        # (Logging not configured here; swallow exception to avoid breaking login)
        pass

    return {"access_token": access_token, "token_type": "bearer"}

from fastapi import status

@app.put("/saved_games/{game_id}", response_model=SavedGameDTO)
def update_saved_game(
    game_id: int,
    game_data: SavedGameCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    game = db.query(SavedGame).filter(SavedGame.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Saved game not found")
    if game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    # Update fields
    game.world_id = game_data.world_id
    game.rating_id = game_data.rating_id
    game.player_name = game_data.player_name
    game.player_gender = game_data.player_gender
    game.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(game)

    return game

@app.post("/saved_games/", response_model=SavedGameIdResponse, status_code=201)
def create_saved_game(
    game_data: SavedGameCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if game_data.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: user mismatch")
    new_game = SavedGame(
        user_id=game_data.user_id,
        world_id=game_data.world_id,
        rating_id=game_data.rating_id,
        player_name=game_data.player_name,
        player_gender=game_data.player_gender,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_game)
    db.commit()
    db.refresh(new_game)

    # Save history entries if provided
    if game_data.history:
        for idx, entry in enumerate(game_data.history):
            new_history = StoryHistory(
                saved_game_id=new_game.id,
                entry_index=idx,
                text=entry.entry,
                created_at=datetime.utcnow()
            )
            db.add(new_history)

    # Save tokenized history blocks if provided
    if game_data.tokenized_history:
        for th in game_data.tokenized_history:
            new_th = TokenizedHistory(
                saved_game_id=new_game.id,
                start_index=th.start_index,
                end_index=th.end_index,
                summary=th.summary,
                created_at=datetime.utcnow()
            )
            db.add(new_th)

    db.commit()
    # Ensure initial history entries get token counts
    check_and_tokenize_history(new_game.id, db, username=current_user.username)
    return {"id": new_game.id}

@app.delete("/saved_games/{game_id}", response_model=dict)
def delete_saved_game(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    game = db.query(SavedGame).filter(SavedGame.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Saved game not found")
    if game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    db.delete(game)
    db.commit()
    return {"detail": "Saved game deleted"}

@app.get("/history/{saved_game_id}", response_model=List[HistoryDTO])
def get_history_for_saved_game(
    saved_game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    game = db.query(SavedGame).filter(SavedGame.id == saved_game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Saved game not found")
    if game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    history_entries = db.query(StoryHistory).filter(StoryHistory.saved_game_id == saved_game_id).all()
    return [history_to_dto(h) for h in history_entries]

@app.post("/history/", response_model=HistoryDTO, status_code=201)
def create_history_entry(
    history_data: HistoryIn,
    saved_game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    game = db.query(SavedGame).filter(SavedGame.id == saved_game_id).first()
    if not game or game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    max_entry_index = db.query(func.max(StoryHistory.entry_index)).filter(StoryHistory.saved_game_id == saved_game_id).scalar()
    next_entry_index = (max_entry_index or -1) + 1
    new_history = StoryHistory(
        saved_game_id=saved_game_id,
        entry_index=next_entry_index,
        text=history_data.entry,  # <-- CORRECT
        created_at=datetime.utcnow()
    )
    db.add(new_history)
    db.commit()
    db.refresh(new_history)
    
    # Update game timestamp
    game.updated_at = datetime.utcnow()
    db.commit()
    
    # TODO: Check if tokenization is needed and queue background task
    # For now, just check synchronously
    check_and_tokenize_history(saved_game_id, db, username=current_user.username)
    
    return history_to_dto(new_history)

def check_and_tokenize_history(saved_game_id: int, db: Session, username: str = None):
    """
    Token-based history compression system:
    - Calculate token counts for all history entries
    - Create tokenized chunks when untokenized entries exceed token limit
    - Mark history entries as tokenized and track references
    - Refine the most recent tokenized chunk when new tokens are added to it
    """
    from ai_settings import get_memory_limits, get_setting
    from token_utils import count_tokens_batch
    from ai_client_requests import ai_summarize_chunk
    
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
    entries_needing_counts = [h for h in all_history if h.token_count is None]
    if entries_needing_counts:
        texts = [h.text for h in entries_needing_counts]
        token_counts = count_tokens_batch(texts)
        for entry, count in zip(entries_needing_counts, token_counts):
            entry.token_count = count
        db.commit()
    
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
        chunk_entries = untokenized
        
        if latest_tokenized and latest_tokenized.token_count:
            # Calculate if the latest chunk is less than 90% of target size
            utilization = latest_tokenized.token_count / TOKENIZED_HISTORY_BLOCK_SIZE
            if utilization < 0.9:
                should_merge = True
                # Get the history entries referenced by the latest chunk
                if latest_tokenized.history_references:
                    ref_ids = [int(id.strip()) for id in latest_tokenized.history_references.split(',')]
                    ref_entries = db.query(StoryHistory).filter(StoryHistory.id.in_(ref_ids)).all()
                    # Merge: old chunk entries + new untokenized entries
                    chunk_entries = ref_entries + untokenized
        
        # Summarize the chunk (either merged or new)
        # Get previous chunk summary for context (not the one we're updating)
        previous_summary = None
        if should_merge:
            # When merging, get the chunk BEFORE the one we're updating
            previous_chunk = db.query(TokenizedHistory).filter(
                TokenizedHistory.saved_game_id == saved_game_id,
                TokenizedHistory.end_index < latest_tokenized.start_index
            ).order_by(TokenizedHistory.end_index.desc()).first()
            if previous_chunk:
                previous_summary = previous_chunk.summary
        else:
            # When creating new chunk, use the latest existing chunk as context
            if latest_tokenized:
                previous_summary = latest_tokenized.summary
        
        chunk_text = [e.text for e in chunk_entries]
        summary = ai_summarize_chunk(chunk_text, TOKENIZED_HISTORY_BLOCK_SIZE, previous_summary=previous_summary, username=username)
        summary_token_count = count_tokens_batch([summary])[0]
        
        # Create history references string
        history_ids = [str(e.id) for e in chunk_entries]
        history_references = ','.join(history_ids)
        
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
                created_at=datetime.utcnow()
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
    from ai_settings import get_setting
    from token_utils import count_tokens_batch
    
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
    prompt = (
        "Compress these story summaries into a single ultra-concise deep memory.\n"
        "Extract ONLY the most critical information:\n"
        "  - Major plot arcs and their resolutions\n"
        "  - Significant character introductions and relationship shifts\n"
        "  - World-changing events or discoveries\n"
        "  - Ongoing missions or tasks\n"
        "Remove ALL minor details, scene descriptions, and redundant information.\n"
        "# Summaries to Compress:\n\n"
        + "\n\n---\n\n".join(summaries_to_merge)
    )
    
    # Use AI to compress (reuse summarize endpoint with custom prompt)
    from ai_client_requests import ai_summarize_chunk
    # Pass the combined summaries as a single chunk
    deep_summary = ai_summarize_chunk([prompt], max_tokens=DEEP_MEMORY_MAX_TOKENS, previous_summary=None, username=username)
    deep_token_count = count_tokens_batch([deep_summary])[0]
    
    if deep_memory:
        # Update existing deep memory
        deep_memory.summary = deep_summary
        deep_memory.token_count = deep_token_count
        deep_memory.chunks_merged += len(old_chunks)
        deep_memory.last_merged_end_index = old_chunks[-1].end_index
        deep_memory.updated_at = datetime.utcnow()
        print(f"Updated deep memory: {deep_memory.chunks_merged} total chunks compressed")
    else:
        # Create new deep memory
        deep_memory = DeepMemory(
            saved_game_id=saved_game_id,
            summary=deep_summary,
            token_count=deep_token_count,
            chunks_merged=len(old_chunks),
            last_merged_end_index=old_chunks[-1].end_index,
            created_at=datetime.utcnow()
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

@app.delete("/history/{history_id}", response_model=dict)
def delete_history_entry(
    history_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    history_entry = db.query(StoryHistory).filter(StoryHistory.id == history_id).first()
    if not history_entry:
        raise HTTPException(status_code=404, detail="History entry not found")
    game = db.query(SavedGame).filter(SavedGame.id == history_entry.saved_game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Saved game not found")
    if game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    
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

@app.put("/history/{history_id}", response_model=HistoryDTO)
def update_history_entry(
    history_id: int,
    update_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from token_utils import count_tokens_batch
    
    history_entry = db.query(StoryHistory).filter(StoryHistory.id == history_id).first()
    if not history_entry:
        raise HTTPException(status_code=404, detail="History entry not found")
    game = db.query(SavedGame).filter(SavedGame.id == history_entry.saved_game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Saved game not found")
    if game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    
    # Update the text field (model uses 'text', not 'entry')
    if "text" in update_data:
        history_entry.text = update_data["text"]
        # Recalculate token count for the modified entry
        history_entry.token_count = count_tokens_batch([history_entry.text])[0]
    
    db.commit()
    db.refresh(history_entry)
    return HistoryDTO.model_validate(history_entry)

@app.post("/tokenized_history/", response_model=TokenizedHistoryDTO, status_code=201)
def create_tokenized_history_entry(
    th_data: TokenizedHistoryIn,
    saved_game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    game = db.query(SavedGame).filter(SavedGame.id == saved_game_id).first()
    if not game or game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    new_th = TokenizedHistory(
        saved_game_id=saved_game_id,
        start_index=th_data.start_index,
        end_index=th_data.end_index,
        summary=th_data.summary,
        created_at=datetime.now(datetime.timezone.utc)
    )
    db.add(new_th)
    db.commit()
    db.refresh(new_th)
    return tokenized_history_to_dto(new_th)

@app.put("/tokenized_history/{tokenized_id}", response_model=TokenizedHistoryDTO)
def update_tokenized_history_entry(
    tokenized_id: int,
    update_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from token_utils import count_tokens_batch
    
    tokenized_entry = db.query(TokenizedHistory).filter(TokenizedHistory.id == tokenized_id).first()
    if not tokenized_entry:
        raise HTTPException(status_code=404, detail="Tokenized history entry not found")
    game = db.query(SavedGame).filter(SavedGame.id == tokenized_entry.saved_game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Saved game not found")
    if game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    
    # Update allowed fields
    if "summary" in update_data:
        tokenized_entry.summary = update_data["summary"]
        # Recalculate token count for the modified summary
        tokenized_entry.token_count = count_tokens_batch([tokenized_entry.summary])[0]
    if "start_index" in update_data:
        tokenized_entry.start_index = update_data["start_index"]
    if "end_index" in update_data:
        tokenized_entry.end_index = update_data["end_index"]
    
    db.commit()
    db.refresh(tokenized_entry)
    return tokenized_history_to_dto(tokenized_entry)

@app.delete("/tokenized_history/{tokenized_id}")
def delete_tokenized_history_entry(
    tokenized_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    tokenized_entry = db.query(TokenizedHistory).filter(TokenizedHistory.id == tokenized_id).first()
    if not tokenized_entry:
        raise HTTPException(status_code=404, detail="Tokenized history entry not found")
    game = db.query(SavedGame).filter(SavedGame.id == tokenized_entry.saved_game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Saved game not found")
    if game.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    
    db.delete(tokenized_entry)
    db.commit()
    return {"detail": "Tokenized history entry deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)