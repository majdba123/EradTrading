from pydantic import BaseModel
from typing import Optional


class UserLogin(BaseModel):
    phone: str
    passcode: str


class UserCreate(BaseModel):
    phone: str
    passcode: str
    type: Optional[int] = 0  # القيمة الافتراضية 0


class TokenResponse(BaseModel):
    access_token: str
    message: str
    user_type: int
    otp_required: bool
