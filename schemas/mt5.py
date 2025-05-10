from pydantic import BaseModel
from typing import Optional

class MT5AccountCreate(BaseModel):
    account_type: str  # STANDARD, PRO, INVEST, MICRO, WALLET

class MT5AccountInfo(BaseModel):
    login: int
    info: dict
    success: bool

class MT5DepositWithdraw(BaseModel):
    amount: float
    comment: Optional[str] = None

class MT5Transfer(BaseModel):
    from_login: int
    to_login: int
    amount: float

class MT5PasswordChange(BaseModel):
   # new_password: str
    password_type: str  # MAIN or INVESTOR