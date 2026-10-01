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


def init_db_schema():
    """Create the database schema.

    This is called explicitly from the DATA server's startup path (which owns
    the database) so a broken connection, bad credentials, or missing ODBC
    driver fails startup loudly instead of being silently swallowed.

    DB-less inference processes (the AI / authoring servers) intentionally do
    NOT call this: they only need the DB for optional auth lookups and must be
    able to boot without SQL Server access.
    """
    Base.metadata.create_all(bind=engine)

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

