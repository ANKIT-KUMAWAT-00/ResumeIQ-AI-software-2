from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class StrictAuthModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

class RegisterRequest(StrictAuthModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    password: str = Field(min_length=8, max_length=128)

class LoginRequest(StrictAuthModel):
    email: EmailStr | None = None
    phone: str | None = None
    password: str | None = None
    code: str | None = None

class VerifyEmailRequest(StrictAuthModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)

class VerifyPhoneRequest(StrictAuthModel):
    phone: str = Field(min_length=6, max_length=30)
    code: str = Field(min_length=6, max_length=6)

class ResendVerificationRequest(StrictAuthModel):
    identifier: str = Field(min_length=3, max_length=254)
    verification_type: Literal["email", "phone"] = "email"

class ForgotPasswordRequest(StrictAuthModel):
    email: EmailStr

class ResetPasswordRequest(StrictAuthModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=128)

class UserResponse(StrictAuthModel):
    id: int
    full_name: str | None = None
    email: str
    phone: str | None = None
    role: str
    email_verified: bool = False
    phone_verified: bool = False
    account_status: str = "active"
    created_at: str

