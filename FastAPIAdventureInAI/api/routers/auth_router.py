"""
Authentication routes.
Handles user registration and login (JWT token generation).
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from shared.services.orm_service import get_db
from shared.services.auth_service import authenticate_user, create_access_token, get_password_hash, get_user_by_username
from business.schemas import UserRegister, Token
from business.dtos import UserDTO
from business.models import User, SessionModel
from config import ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(tags=["authentication"])


@router.post("/register/", response_model=UserDTO)
async def register(user: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user account.
    
    Creates a new user with hashed password.
    Returns 400 if username already exists.
    """
    if get_user_by_username(db, user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    db_user = User(username=user.username, email=user.email, password_hash=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login endpoint - authenticate user and return JWT access token.
    
    Uses OAuth2 password flow (form data with username and password).
    Returns access token that must be included in subsequent requests.
    """
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
