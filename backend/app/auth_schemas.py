from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.auth_models import UserRole
import email_validator
email_validator.TEST_ENVIRONMENT = True


class UserSignup(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    role: UserRole = UserRole.citizen
    district: Optional[str] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email": "doctor@example.com", "password": "strongpassword123",
            "full_name": "Dr. Rahim Uddin", "role": "hospital", "district": "Munshiganj"
        }
    })


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str
    # This is consumed by the local frontend until an email provider is configured.
    reset_token: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    district: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
