from sqlalchemy.orm import Session
from aiadventureinpythonconstants import (
    GAME_RATINGS,
    STORY_SETUPS,
    STORYTELLER_PROMPT,
    SUMMARY_SPLIT_MARKER,
    GAME_DIRECTIVE,
    STOP_TOKENS,
    RECENT_MEMORY_LIMIT,
    MEMORY_BACKLOG_LIMIT,
    TOKENIZE_HISTORY_CHUNK_SIZE,
    TOKENIZE_THRESHOLD,
    MAX_TOKENIZED_HISTORY_BLOCK,
    TOKENIZED_HISTORY_BLOCK_SIZE,
    DEEP_MEMORY_MAX_TOKENS,
    SUMMARY_MIN_TOKEN_PERCENT,
    MAX_TOKENS,
    RESERVED_FOR_GENERATION,
    SAFE_PROMPT_LIMIT,
    MAX_WORLD_TOKENS
)
from dependencies import SessionLocal
from business.models import GameRating, World, AIDirectiveSettings, AccountLevel, User


########################## METHODS  IN THIS HAVE BEEN COMMENTED OUT TO PREVENT DATA OVERWRITES, BUT LEFT FOR SEEDING PURPOSES ##########################

def seed_game_ratings():
    """Seed default game ratings (content filters)."""
    from aiadventureinpythonconstants import GAME_RATING_PROMPTS
    db: Session = SessionLocal()
    if db.query(GameRating).count() > 0:
        print("GameRatings already exist. Skipping game ratings seeding.")
        db.close()
        return
    for idx, (name, ai_prompt) in enumerate(zip(GAME_RATINGS, GAME_RATING_PROMPTS)):
        db.add(GameRating(id=idx+1, name=name, ai_prompt=ai_prompt))
        print(f"Created GameRating: {name}")
    db.commit()
    db.close()

def seed_worlds():
    db: Session = SessionLocal()
    # Check if any worlds exist
    if db.query(World).count() > 0:
        print("Worlds already exist. Skipping world seeding.")
        db.close()
        return
    # Find admin user
    admin = db.query(User).filter_by(username="admin").first()
    admin_id = admin.id if admin else None
    from aiadventureinpythonconstants import STORY_SETUPS
    for name, setup in STORY_SETUPS.items():
        db.add(World(
            user_id=admin_id,
            name=name,
            preface=setup["preface"],
            world_tokens=setup["world_tokens"]
        ))
        print(f"Created world: {name} (user_id={admin_id})")
    db.commit()
    db.close()

def seed_ai_directive_settings():
    db: Session = SessionLocal()
    if db.query(AIDirectiveSettings).count() > 0:
        print("AI Directive Settings already exist. Skipping directive settings seeding.")
        db.close()
        return
    
    # Basic settings (ID=1) - more restrictive
    basic = db.query(AIDirectiveSettings).filter_by(id=1).first()
    basic_prompt = (
        "You are the Narrator of an interactive text adventure. Write in 3rd person.\n\n"
        "Response Format:\n"
        "• 1-2 short paragraphs\n"
        "• Advance plot through action or dialogue\n"
        "• Keep descriptions brief\n\n"
        "Continuity:\n"
        "• Use Past History for context, Recent Story for immediate events\n"
        "• Never repeat prior entries\n\n"
        "Constraints:\n"
        "• Stay within the universe tone\n"
        "• Respect player narrative control\n"
    )
    
    if basic:
        basic.storyteller_prompt = basic_prompt
        basic.recent_memory_limit = 8
        basic.memory_backlog_limit = 8
        basic.tokenize_history_chunk_size = 8
        basic.tokenize_threshold = 600
        basic.max_tokenized_history_block = 4
        basic.tokenized_history_block_size = 150
        basic.deep_memory_max_tokens = 200
        basic.max_world_tokens = 500
        print("Updated Basic AI settings (ID=1).")
    else:
        basic = AIDirectiveSettings(
            id=1,
            storyteller_prompt=basic_prompt,
            game_directive=GAME_DIRECTIVE,
            summary_split_marker=SUMMARY_SPLIT_MARKER,
            stop_tokens=",".join(STOP_TOKENS),
            recent_memory_limit=8,
            memory_backlog_limit=8,
            tokenize_history_chunk_size=8,
            tokenize_threshold=600,
            max_tokenized_history_block=4,
            tokenized_history_block_size=150,
            deep_memory_max_tokens=200,
            summary_min_token_percent=SUMMARY_MIN_TOKEN_PERCENT,
            max_tokens=MAX_TOKENS,
            reserved_for_generation=RESERVED_FOR_GENERATION,
            safe_prompt_limit=SAFE_PROMPT_LIMIT,
            max_world_tokens=500
        )
        db.add(basic)
        print("Created Basic AI settings (ID=1).")
    
    # Elite settings (ID=2) - full featured
    elite = db.query(AIDirectiveSettings).filter_by(id=2).first()
    
    if elite:
        elite.storyteller_prompt = STORYTELLER_PROMPT
        elite.game_directive = GAME_DIRECTIVE
        elite.summary_split_marker = SUMMARY_SPLIT_MARKER
        elite.stop_tokens = ",".join(STOP_TOKENS)
        elite.recent_memory_limit = RECENT_MEMORY_LIMIT
        elite.memory_backlog_limit = MEMORY_BACKLOG_LIMIT
        elite.tokenize_history_chunk_size = TOKENIZE_HISTORY_CHUNK_SIZE
        elite.tokenize_threshold = TOKENIZE_THRESHOLD
        elite.max_tokenized_history_block = MAX_TOKENIZED_HISTORY_BLOCK
        elite.tokenized_history_block_size = TOKENIZED_HISTORY_BLOCK_SIZE
        elite.deep_memory_max_tokens = DEEP_MEMORY_MAX_TOKENS
        elite.summary_min_token_percent = SUMMARY_MIN_TOKEN_PERCENT
        elite.max_tokens = MAX_TOKENS
        elite.reserved_for_generation = RESERVED_FOR_GENERATION
        elite.safe_prompt_limit = SAFE_PROMPT_LIMIT
        elite.max_world_tokens = MAX_WORLD_TOKENS
        print("Updated Elite AI settings (ID=2).")
    else:
        elite = AIDirectiveSettings(
            id=2,
            storyteller_prompt=STORYTELLER_PROMPT,
            game_directive=GAME_DIRECTIVE,
            summary_split_marker=SUMMARY_SPLIT_MARKER,
            stop_tokens=",".join(STOP_TOKENS),
            recent_memory_limit=RECENT_MEMORY_LIMIT,
            memory_backlog_limit=MEMORY_BACKLOG_LIMIT,
            tokenize_history_chunk_size=TOKENIZE_HISTORY_CHUNK_SIZE,
            tokenize_threshold=TOKENIZE_THRESHOLD,
            max_tokenized_history_block=MAX_TOKENIZED_HISTORY_BLOCK,
            tokenized_history_block_size=TOKENIZED_HISTORY_BLOCK_SIZE,
            deep_memory_max_tokens=DEEP_MEMORY_MAX_TOKENS,
            summary_min_token_percent=SUMMARY_MIN_TOKEN_PERCENT,
            max_tokens=MAX_TOKENS,
            reserved_for_generation=RESERVED_FOR_GENERATION,
            safe_prompt_limit=SAFE_PROMPT_LIMIT,
            max_world_tokens=MAX_WORLD_TOKENS
        )
        db.add(elite)
        print("Created Elite AI settings (ID=2).")
    
    db.commit()
    db.close()

def seed_account_levels():
    db: Session = SessionLocal()
    if db.query(AccountLevel).count() > 0:
        print("Account levels already exist. Skipping account levels seeding.")
        db.close()
        return
    
    # Basic account level
    basic_level = db.query(AccountLevel).filter_by(name="Basic").first()
    if basic_level:
        basic_level.game_settings_id = 1
        print("Updated Basic account level.")
    else:
        basic_level = AccountLevel(id=1, name="Basic", game_settings_id=1)
        db.add(basic_level)
        print("Created Basic account level.")
    
    # Elite account level
    elite_level = db.query(AccountLevel).filter_by(name="Elite").first()
    if elite_level:
        elite_level.game_settings_id = 2
        print("Updated Elite account level.")
    else:
        elite_level = AccountLevel(id=2, name="Elite", game_settings_id=2)
        db.add(elite_level)
        print("Created Elite account level.")
    
    db.commit()
    
    # Update admin user to Elite
    admin = db.query(User).filter_by(username="admin").first()
    if admin:
        admin.account_level_id = 2
        db.commit()
        print("Set admin user to Elite account level.")
    else:
        print("Warning: admin user not found.")
    
    db.close()

def seed_admin_user():
    """Create default admin user if it doesn't exist."""
    from services.auth_service import get_password_hash
    db: Session = SessionLocal()
    if db.query(User).filter_by(username="admin").count() > 0:
        print("Admin user already exists. Skipping admin seeding.")
        db.close()
        return
    # Create admin user with default password 'admin123'
    admin = User(
        username="admin",
        hashed_password=get_password_hash("admin123"),
        email="admin@localhost",
        account_level_id=2  # Elite level
    )
    db.add(admin)
    db.commit()
    print("Created admin user (username: admin, password: admin123)")
    print("IMPORTANT: Change the admin password after first login!")
    db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Starting database seeding...")
    print("=" * 60)
    
    seed_game_ratings()
    seed_worlds()
    seed_ai_directive_settings()
    seed_account_levels()
    seed_admin_user()
    
    print("=" * 60)
    print("Database seeding complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Start AI server: python ai_server.py")
    print("2. Start API server: python main.py")
    print("3. Login with username: admin, password: admin123")
    print("4. CHANGE THE ADMIN PASSWORD!")
    print("=" * 60)