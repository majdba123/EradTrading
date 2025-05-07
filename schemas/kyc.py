from pydantic import BaseModel
from typing import Optional
from enum import Enum

class KYCStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class KYCDocumentType(str, Enum):
    ID_CARD = "id_card"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"

class KYCCreate(BaseModel):
    user_id: int
    document_type: KYCDocumentType
    document_number: str
    front_image_url: str
    back_image_url: Optional[str] = None
    selfie_image_url: str

class KYCUpdate(BaseModel):
    status: KYCStatus
    rejection_reason: Optional[str] = None

class KYCResponse(KYCCreate):
    id: int
    status: KYCStatus
    created_at: str
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[int] = None