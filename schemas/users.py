from pydantic import BaseModel
from typing import Optional

class UserLogin(BaseModel):
    phone: str
    passcode: str
    password: str  # Changed from passcode to password


class UserRegister(BaseModel):
    phone: str
    first_name: str
    last_name: str
    password: str
    passcode: str

class TokenResponse(BaseModel):
    access_token: str
    message: str
    user_type: int
    otp_required: bool

class ManagerCreate(BaseModel):
    phone: str
    name: str
    passcode: str

class ManagerFilter(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    page: Optional[int] = 1
    per_page: Optional[int] = 10

class UserStatusUpdate(BaseModel):
    user_id: int
    new_status: str  # يمكن أن يكون: 'pending', 'approved', 'rejected', 'banned'
    
    
    
