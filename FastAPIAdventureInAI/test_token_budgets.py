"""
Test script to calculate total token budget for AI prompts.
Analyzes all world setups and calculates maximum prompt size.
Uses actual database settings for both Basic and Elite tiers via account_levels join.
"""
from transformers import AutoTokenizer
from aiadventureinpythonconstants import STORY_SETUPS
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
from models import AIDirectiveSettings, AccountLevel

# Load the same tokenizer used by the AI
AI_MODEL = "TheBloke/MythoMax-L2-13B-GPTQ"
print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(AI_MODEL, use_fast=True)
print("✓ Tokenizer loaded\n")

# Connect to database
print("Connecting to database...")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()
print("✓ Database connected\n")

# Show account level mappings
print("="*80)
print("ACCOUNT LEVEL MAPPINGS")
print("="*80)
account_levels = db.query(AccountLevel).all()
for level in account_levels:
    settings = db.query(AIDirectiveSettings).filter_by(id=level.game_settings_id).first()
    print(f"{level.name} (ID={level.id}) → Game Settings ID={level.game_settings_id}")
    if settings:
        print(f"  Settings: {settings.max_tokenized_history_block} chunks × {settings.tokenized_history_block_size} tokens")
        print(f"  Recent History Threshold: {settings.tokenize_threshold} tokens")
print()

def count_tokens(text):
    """Count tokens in a text string."""
    return len(tokenizer.encode(text, add_special_tokens=False))

def test_account_level(account_level_name):
    """Test token budget for a specific account level."""
    
    # Load account level and its settings from database
    account_level = db.query(AccountLevel).filter_by(name=account_level_name).first()
    if not account_level:
        print(f"✗ Account level '{account_level_name}' not found in database!")
        return
    
    settings = db.query(AIDirectiveSettings).filter_by(id=account_level.game_settings_id).first()
    if not settings:
        print(f"✗ Settings ID {account_level.game_settings_id} not found in database!")
        return
    
    print("="*80)
    print(f"{account_level_name.upper()} ACCOUNT LEVEL (ID={account_level.id})")
    print(f"Game Settings ID: {account_level.game_settings_id}")
    print("="*80)
    
    STORYTELLER_PROMPT = settings.storyteller_prompt
    MAX_TOKENIZED_HISTORY_BLOCK = settings.max_tokenized_history_block
    TOKENIZED_HISTORY_BLOCK_SIZE = settings.tokenized_history_block_size
    TOKENIZE_THRESHOLD = settings.tokenize_threshold
    MAX_TOKENS = settings.max_tokens
    RESERVED_FOR_GENERATION = settings.reserved_for_generation
    DEEP_MEMORY_MAX_TOKENS = settings.deep_memory_max_tokens
    
    print(f"Settings:")
    print(f"  Max Tokenized History Blocks: {MAX_TOKENIZED_HISTORY_BLOCK}")
    print(f"  Tokenized History Block Size: {TOKENIZED_HISTORY_BLOCK_SIZE} tokens")
    print(f"  Tokenize Threshold: {TOKENIZE_THRESHOLD} tokens")
    print(f"  Deep Memory Max Tokens: {DEEP_MEMORY_MAX_TOKENS} tokens")
    print(f"  Max Tokens: {MAX_TOKENS}")
    print(f"  Reserved for Generation: {RESERVED_FOR_GENERATION}")
    print()
    
    # Test each world
    print("WORLD TOKEN ANALYSIS")
    print("-" * 80)
    
    world_results = []
    for world_name, setup in STORY_SETUPS.items():
        world_text = f"{world_name}\n{setup['world_tokens']}\n{setup['preface']}"
        token_count = count_tokens(world_text)
        world_results.append((world_name, token_count))
        print(f"{world_name}:")
        print(f"  World Tokens: {count_tokens(setup['world_tokens'])}")
        print(f"  Preface: {count_tokens(setup['preface'])}")
        print(f"  Name: {count_tokens(world_name)}")
        print(f"  TOTAL: {token_count} tokens\n")
    
    max_world = max(world_results, key=lambda x: x[1])
    print(f"Largest World: {max_world[0]} ({max_world[1]} tokens)")
    print()
    
    # Calculate fixed prompt scaffolding
    print("PROMPT SCAFFOLDING TOKEN ANALYSIS")
    print("-" * 80)
    
    scaffolding_parts = {
        "Narrator Directives": STORYTELLER_PROMPT,
        "Headers (Universe, Preface, Player, Rating, etc.)": "# Narrator Directives:\n\n# Universe: \n\n# Story Preface:\n\n# Player:  ()\n# Rating: \n\n",
        "Ancient History header": "# Ancient History (Major Events):\n",
        "Past Events header": "# Past Events:\n",
        "Recent Story header": "# Recent Story:\n",
        "Player Action headers": "# Player Action: \n\n",
        "Story Splitter": "###\n"
    }
    
    total_scaffolding = 0
    for part_name, text in scaffolding_parts.items():
        tokens = count_tokens(text)
        total_scaffolding += tokens
        print(f"{part_name}: {tokens} tokens")
    
    print(f"\nTotal Scaffolding: {total_scaffolding} tokens")
    
    # Player info tokens (max estimate)
    player_name_max = 5  # "Judas" type names
    player_gender = count_tokens("Male")  # or Female
    player_info_tokens = player_name_max + player_gender + count_tokens("Player: ")
    print(f"Player Info (max estimate): {player_info_tokens} tokens")
    
    # Memory budget
    print()
    print("MEMORY BUDGET")
    print("-" * 80)
    deep_memory_tokens = DEEP_MEMORY_MAX_TOKENS
    tokenized_history_tokens = MAX_TOKENIZED_HISTORY_BLOCK * TOKENIZED_HISTORY_BLOCK_SIZE
    recent_history_tokens = TOKENIZE_THRESHOLD
    
    print(f"Deep Memory: {deep_memory_tokens} tokens")
    print(f"Tokenized History ({MAX_TOKENIZED_HISTORY_BLOCK} chunks × {TOKENIZED_HISTORY_BLOCK_SIZE}): {tokenized_history_tokens} tokens")
    print(f"Recent History (up to): {recent_history_tokens} tokens")
    print(f"Total Memory Budget: {deep_memory_tokens + tokenized_history_tokens + recent_history_tokens} tokens")
    
    # Calculate total worst-case prompt size
    print()
    print("WORST-CASE TOTAL PROMPT SIZE")
    print("-" * 80)
    
    worst_case = (
        total_scaffolding +
        player_info_tokens +
        max_world[1] +  # Largest world
        deep_memory_tokens +
        tokenized_history_tokens +
        recent_history_tokens
    )
    
    print(f"Scaffolding: {total_scaffolding} tokens")
    print(f"Player Info: {player_info_tokens} tokens")
    print(f"World (largest): {max_world[1]} tokens")
    print(f"Deep Memory: {deep_memory_tokens} tokens")
    print(f"Tokenized History: {tokenized_history_tokens} tokens")
    print(f"Recent History: {recent_history_tokens} tokens")
    print(f"─" * 80)
    print(f"TOTAL PROMPT: {worst_case} tokens")
    print(f"\nModel Limit: {MAX_TOKENS} tokens")
    print(f"Reserved for Generation: {RESERVED_FOR_GENERATION} tokens")
    print(f"Safe Prompt Limit: {MAX_TOKENS - RESERVED_FOR_GENERATION} tokens")
    
    safe_limit = MAX_TOKENS - RESERVED_FOR_GENERATION
    if worst_case <= safe_limit:
        print(f"\n✓ SAFE")
        print(f"Headroom: {safe_limit - worst_case} tokens")
    else:
        overage = worst_case - safe_limit
        print(f"\n✗ EXCEEDS LIMIT by {overage} tokens")
        print(f"\nSuggested adjustments:")
        print(f"  - Reduce Deep Memory: {deep_memory_tokens} → {max(100, deep_memory_tokens - overage)} tokens")
        print(f"  - Reduce Tokenized History chunks: {MAX_TOKENIZED_HISTORY_BLOCK} → {max(3, MAX_TOKENIZED_HISTORY_BLOCK - 1)}")
        print(f"  - Reduce Recent History threshold: {recent_history_tokens} → {max(400, recent_history_tokens - overage)}")
    
    print("\n")

# Test Basic account level
test_account_level("Basic")

# Test Elite account level
test_account_level("Elite")

db.close()
print("="*80)
print("ANALYSIS COMPLETE")
print("="*80)
