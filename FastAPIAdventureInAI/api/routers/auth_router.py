"""
Authentication routes.
Handles user registration and login (JWT token generation).
"""
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from shared.services.orm_service import get_db
from business.schemas import UserRegister, Token
from business.dtos import UserDTO

from api.services.data_api_auth_service import  (
    perform_register,
    perform_login,
)

router = APIRouter(tags=["authentication"])


@router.post("/register/", response_model=UserDTO)
async def register(user: UserRegister, db: Session = Depends(get_db)):
    return await perform_register(user, db)

@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return await perform_login(form_data, db)