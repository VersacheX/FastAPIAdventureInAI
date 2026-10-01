"""
Shared dependencies for FastAPI application.
Contains database session management and authentication dependencies.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from jose import JWTError, jwt

from config import DATABASE_URL, SECRET_KEY, ALGORITHM
from business.models import Base, User

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Attempt to create tables at import time, but don't hard-fail startup if the
# database is unreachable or the ODBC driver isn't installed. This lets the AI
# server (which only needs the DB for auth) boot in environments without SQL
# Server access. DB-dependent endpoints will still raise when actually used.
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:  # pragma: no cover - environment dependent
    import sys
    print(f"[orm_service] WARNING: could not initialize database schema: {e}", file=sys.stderr)

def get_db():
    """
    Dependency that provides a database session.
    Automatically closes the session after the request is complete.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

