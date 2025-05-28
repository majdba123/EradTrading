from fastapi import Request, Response, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Optional
import secrets
from datetime import datetime, timedelta
from database.connection import get_db_connection

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
        # التحقق من أن المستخدم غير محظور قبل إنشاء الجلسة
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT status FROM users WHERE id = ?",
                (user_id,)
            )
            user_status = cursor.fetchone()
            
            if not user_status:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="المستخدم غير موجود"
                )
                
            if user_status[0] == 'banned':
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="حسابك محظور ولا يمكنك تسجيل الدخول"
                )
                
        finally:
            if conn:
                conn.close()

        token = TokenHandler.generate_token()
        expires_at = datetime.now() + timedelta(hours=24)  # صلاحية 24 ساعة

        sessions_cache[token] = {
            "user_id": user_id,
            "user_type": user_type,
            "expires_at": expires_at,
            "created_at": datetime.now()
        }
        return token

    @staticmethod
    def validate_token(token: str) -> Optional[dict]:
        """التحقق من صحة التوكن"""
        if token not in sessions_cache:
            return None

        session = sessions_cache[token]
        
        # التحقق من انتهاء الصلاحية
        if datetime.now() > session["expires_at"]:
            del sessions_cache[token]  # حذف التوكن إذا انتهت صلاحيته
            return None

        # التحقق من أن المستخدم غير محظور في قاعدة البيانات
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT status FROM users WHERE id = ?",
                (session["user_id"],)
            )
            
            user_status = cursor.fetchone()
            
            if not user_status or user_status[0] == 'banned':
                # إذا كان المستخدم محظوراً أو غير موجود، نحذف الجلسة
                del sessions_cache[token]
                return None
                
        except Exception as e:
            # في حالة حدوث خطأ، نعتبر الجلسة غير صالحة
            del sessions_cache[token]
            return None
        finally:
            if conn:
                conn.close()

        return session

    @staticmethod
    def delete_session(token: str):
        """حذف جلسة المستخدم (تسجيل الخروج)"""
        if token in sessions_cache:
            del sessions_cache[token]

    @staticmethod
    def delete_all_user_sessions(user_id: int):
        """حذف جميع جلسات المستخدم (عند حظره أو تغيير كلمة المرور)"""
        global sessions_cache
        sessions_cache = {
            token: session for token, session in sessions_cache.items() 
            if session["user_id"] != user_id
        }


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