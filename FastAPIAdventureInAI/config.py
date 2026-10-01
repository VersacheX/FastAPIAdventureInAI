"""
Configuration management using environment variables with fallback to defaults.
"""
import os
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# Database Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mssql+pyodbc://username:password@HOSTNAME/DATABASE?driver=ODBC+Driver+17+for+SQL+Server"
)

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "4320"))  # 3 days default

# Server URLs
API_SERVER_URL = os.getenv("API_SERVER_URL", "http://localhost:8080")
AI_SERVER_URL = os.getenv("AI_SERVER_URL", "http://localhost:9000")

# CORS Origins - Allow all origins on local network for mobile access
CORS_ORIGINS = ["*"]  # Allow all origins (change to specific IPs in production)

# Story AI model (llama.cpp / GGUF) Configuration
# The AI server now runs a llama.cpp instruct model (e.g. Qwen2.5 / Hermes 2).
STORY_MODEL_PATH = os.getenv(
    "STORY_MODEL_PATH",
    "/home/dmin/models/Qwen2.5-14B_Uncensored_Instruct-Q5_K_M.gguf"
)
STORY_MODEL_CTX = int(os.getenv("STORY_MODEL_CTX", "16384"))
STORY_MODEL_GPU_LAYERS = int(os.getenv("STORY_MODEL_GPU_LAYERS", "-1"))
# Prompt-ingestion batch size. Bigger = faster prompt eval on GPU (more VRAM).
STORY_MODEL_BATCH = int(os.getenv("STORY_MODEL_BATCH", "512"))
# Flash attention: smaller KV cache + faster attention on CUDA. Off by default
# to match the known-good reference loader; enable with "1" if your build
# supports it (it frees VRAM and can speed attention).
STORY_MODEL_FLASH_ATTN = os.getenv("STORY_MODEL_FLASH_ATTN", "0") == "1"

# Authoring AI model (llama.cpp / GGUF) Configuration
# Used by the separate authoring server (port 9100) for structured story
# authoring. Defaults to the same model as the story engine so the server can
# start out of the box; override via environment variables to use a different
# model or offload settings.
AUTHORING_MODEL_PATH = os.getenv("AUTHORING_MODEL_PATH", STORY_MODEL_PATH)
AUTHORING_MODEL_CTX = int(os.getenv("AUTHORING_MODEL_CTX", str(STORY_MODEL_CTX)))
AUTHORING_MODEL_GPU_LAYERS = int(os.getenv("AUTHORING_MODEL_GPU_LAYERS", str(STORY_MODEL_GPU_LAYERS)))

# Remote settings source for the AI server.
# The AI server (e.g. in WSL) cannot reach SQL Server directly. When this URL is
# set, AI settings are fetched over HTTP from the data server (which CAN read the
# DB) instead of hitting the database directly. Leave unset on the data server.
# Example: http://192.168.1.12:8080
SETTINGS_REMOTE_URL = os.getenv("SETTINGS_REMOTE_URL", "")
