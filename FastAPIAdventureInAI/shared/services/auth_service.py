"""
Authentication service.
Handles password hashing, JWT token creation, and user authentication.
"""
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher, exceptions
from jose import jwt
from sqlalchemy.orm import Session
from jose.exceptions import JWTError

# Security
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from fastapi import Request, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer,OAuth2PasswordBearer

from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from business.models import User, SavedGame
from shared.services.orm_service import get_db


security = HTTPBearer()

# Password hashing setup
ph = PasswordHasher()

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def _get_auth_headers():
    """Generate auth headers for AI server requests"""
    # Use 'system' user for internal server-to-server calls
    token = jwt.encode({"sub": "system"}, SECRET_KEY, algorithm=ALGORITHM)
    return {"Authorization": f"Bearer {token}"}

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token from Authorization header"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
        return username
    except ExpiredSignatureError:
        # Token has expired — return401 so frontend can clear local session
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password using Argon2.
    
    Args:
        plain_password: The plain text password to verify
        hashed_password: The hashed password to check against
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        return ph.verify(hashed_password, plain_password)
    except exceptions.VerifyMismatchError:
        return False
    except exceptions.VerificationError:
        return False

def get_password_hash(password: str) -> str:
    """
    Hash a password using Argon2.
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Hashed password string
    """
    return ph.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """
    Authenticate a user by username and password.
    
    Args:
        db: Database session
        username: Username to authenticate
        password: Plain text password to verify
        
    Returns:
        User object if authentication succeeds, None otherwise
    """
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user

def verify_game_ownership(
    game_id: int,
    user_id: int,
    db: Session
) -> SavedGame:
    """
    Verify that a user owns a saved game.
    
    Args:
        game_id: ID of the saved game
        user_id: ID of the user
        db: Database session
        
    Returns:
        The SavedGame if owned by user
        
    Raises:
        ValueError: If game not found or not owned by user
    """
    
    game = db.query(SavedGame).filter(SavedGame.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Saved game not found")
    if game.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: not your saved game")
    
    return game

def get_user_by_username(db: Session, username: str):
    """Helper function to fetch user by username."""
    return db.query(User).filter(User.username == username).first()

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    """
    Dependency that validates JWT token and returns the current authenticated user.
    Raises 401 if token is invalid or user not found.
    """
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
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except (JWTError, InvalidTokenError):
        raise credentials_exception
    
    user = get_user_by_username(db, username)
    if user is None:
        raise credentials_exception
    return user