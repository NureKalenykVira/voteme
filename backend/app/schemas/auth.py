import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.core.enums import Role


_PASSWORD_LETTER_RE = re.compile(r"[A-Za-z]")
_PASSWORD_DIGIT_RE = re.compile(r"\d")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not _PASSWORD_LETTER_RE.search(value):
            raise ValueError("Password must contain at least one letter")
        if not _PASSWORD_DIGIT_RE.search(value):
            raise ValueError("Password must contain at least one digit")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    role: Role
    is_confirmed: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConfirmEmailResponse(BaseModel):
    message: str
