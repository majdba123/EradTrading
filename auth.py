from fastapi import Request, Response, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Optional
import secrets
from datetime import datetime, timedelta

# تخزين الجلسات في الذاكرة (يمكن استبداله بـ Redis في الإنتاج)
sessions_cache: Dict[str, dict] = {}


class TokenHandler:
    @staticmethod
    def generate_token() -> str:
        """إنشاء توكن عشوائي آمن"""
        return secrets.token_hex(32)

    @staticmethod
    def create_session(user_id: int, user_type: int) -> str:
        """إنشاء جلسة جديدة وتخزينها في الكاش"""
        token = TokenHandler.generate_token()
        expires_at = datetime.now() + timedelta(hours=24)  # صلاحية 24 ساعة

        sessions_cache[token] = {
            "user_id": user_id,
            "user_type": user_type,
            "expires_at": expires_at
        }
        return token

    @staticmethod
    def validate_token(token: str) -> Optional[dict]:
        """التحقق من صحة التوكن"""
        if token not in sessions_cache:
            return None

        session = sessions_cache[token]
        if datetime.now() > session["expires_at"]:
            del sessions_cache[token]  # حذف التوكن إذا انتهت صلاحيته
            return None

        return session

    @staticmethod
    def delete_session(token: str):
        """حذف جلسة المستخدم (تسجيل الخروج)"""
        if token in sessions_cache:
            del sessions_cache[token]


class JWTBearer(HTTPBearer):
    """Dependency للتحقق من التوكن في المسارات"""

    async def __call__(self, request: Request) -> dict:
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        if not credentials or credentials.scheme != "Bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing Bearer token",
            )

        session = TokenHandler.validate_token(credentials.credentials)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        # إضافة التوكن نفسه إلى البيانات المرجعة
        session["token"] = credentials.credentials
        return session


auth_scheme = JWTBearer()
