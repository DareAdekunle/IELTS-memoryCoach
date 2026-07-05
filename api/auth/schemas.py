from pydantic import BaseModel, EmailStr
from typing import Optional


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    full_name: Optional[str] = None
    learner_id: Optional[str] = None


class UserResponse(BaseModel):
    user_id: str
    email: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    auth_provider: str
    learner_id: Optional[str] = None


class MessageResponse(BaseModel):
    message: str