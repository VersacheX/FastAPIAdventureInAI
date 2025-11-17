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
    "mssql+pyodbc://sljackson:themagicwordmotherfucker@DESKTOP-3K6IPDC/AIAdventureInPython?driver=ODBC+Driver+17+for+SQL+Server"
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
