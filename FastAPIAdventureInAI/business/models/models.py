from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class GameRating(Base):
    __tablename__ = "game_ratings"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, nullable=False)
    ai_prompt = Column(Text, nullable=False)
    saved_games = relationship("SavedGame", back_populates="rating_obj")

class World(Base):
    __tablename__ = "worlds"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL for system worlds
    name = Column(String(64), unique=True, nullable=False)
    preface = Column(Text, nullable=False)
    world_tokens = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    token_count = Column(Integer, nullable=True)  # NEW: store token count
    user = relationship("User", back_populates="worlds")
    saved_games = relationship("SavedGame", back_populates="world_obj")

class AccountLevel(Base):
    __tablename__ = "account_levels"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, nullable=False)
    game_settings_id = Column(Integer, ForeignKey("ai_directive_settings.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    game_settings = relationship("AIDirectiveSettings")
    users = relationship("User", back_populates="account_level")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    email = Column(String(128), unique=True, nullable=True)
    password_hash = Column(String(128), nullable=False)  
    account_level_id = Column(Integer, ForeignKey("account_levels.id"), nullable=False, server_default='1')
    created_at = Column(DateTime, default=datetime.utcnow)
    account_level = relationship("AccountLevel", back_populates="users")
    saved_games = relationship("SavedGame", back_populates="user")
    worlds = relationship("World", back_populates="user")

class SavedGame(Base):
    __tablename__ = "saved_games"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=False)
    rating_id = Column(Integer, ForeignKey("game_ratings.id"), nullable=False)
    player_name = Column(String(64), nullable=False)
    player_gender = Column(String(16), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="saved_games")
    world_obj = relationship("World", back_populates="saved_games")
    rating_obj = relationship("GameRating", back_populates="saved_games")
    story_history = relationship("StoryHistory", back_populates="saved_game", cascade="all, delete-orphan")
    tokenized_history = relationship("TokenizedHistory", back_populates="saved_game", cascade="all, delete-orphan")
    deep_memory = relationship("DeepMemory", back_populates="saved_game", uselist=False, cascade="all, delete-orphan")

class StoryHistory(Base):
    __tablename__ = "story_history"
    id = Column(Integer, primary_key=True)
    saved_game_id = Column(Integer, ForeignKey("saved_games.id"), nullable=False)
    entry_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)  # Calculated token count for this entry
    is_tokenized = Column(Integer, default=0, nullable=False)  # 0=False, 1=True (SQLite compatibility)
    created_at = Column(DateTime, default=datetime.utcnow)
    saved_game = relationship("SavedGame", back_populates="story_history")

class TokenizedHistory(Base):
    __tablename__ = "tokenized_history"
    id = Column(Integer, primary_key=True)
    saved_game_id = Column(Integer, ForeignKey("saved_games.id"), nullable=False)
    start_index = Column(Integer, nullable=False)
    end_index = Column(Integer, nullable=False)
    summary = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)  # Token count of the summary
    is_tokenized = Column(Integer, default=0, nullable=False)  # 0=Active, 1=Compressed into deep memory
    history_references = Column(Text, nullable=True)  # Comma-separated StoryHistory IDs
    created_at = Column(DateTime, default=datetime.utcnow)
    saved_game = relationship("SavedGame", back_populates="tokenized_history")

class DeepMemory(Base):
    """
    Ultra-compressed memory for ancient history.
    When tokenized chunks exceed max limit, oldest chunks are merged into this single entry.
    This grows over time as the story progresses, containing only the most critical plot points.
    """
    __tablename__ = "deep_memory"
    id = Column(Integer, primary_key=True)
    saved_game_id = Column(Integer, ForeignKey("saved_games.id"), nullable=False, unique=True)
    summary = Column(Text, nullable=False)  # Ultra-compressed summary of merged chunks
    token_count = Column(Integer, nullable=True)  # Token count of the summary
    chunks_merged = Column(Integer, default=0)  # How many tokenized chunks have been merged
    last_merged_end_index = Column(Integer, nullable=True)  # Track up to which history index we've compressed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    saved_game = relationship("SavedGame", back_populates="deep_memory")
    
class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(256), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow)
    user = relationship("User")

class AIDirectiveSettings(Base):
    __tablename__ = 'ai_directive_settings'
    id = Column(Integer, primary_key=True)
    storyteller_prompt = Column(String, nullable=False)
    game_directive = Column(String, nullable=False)
    summary_split_marker = Column(String, nullable=False)
    stop_tokens = Column(String, nullable=False)  # Store as comma-separated string
    recent_memory_limit = Column(Integer, nullable=False)
    memory_backlog_limit = Column(Integer, nullable=False)
    tokenize_history_chunk_size = Column(Integer, nullable=False)
    tokenize_threshold = Column(Integer, nullable=False, server_default='800')  # Token count that triggers compression
    max_tokenized_history_block = Column(Integer, nullable=False)
    tokenized_history_block_size = Column(Integer, nullable=False)
    deep_memory_max_tokens = Column(Integer, nullable=False, server_default='300')  # Maximum tokens for ultra-compressed ancient history
    summary_min_token_percent = Column(Float, nullable=False)
    max_tokens = Column(Integer, nullable=False)
    reserved_for_generation = Column(Integer, nullable=False)
    safe_prompt_limit = Column(Integer, nullable=False)
    max_world_tokens = Column(Integer, nullable=False, server_default='1000')  # Maximum tokens for world creation