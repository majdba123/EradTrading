from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Optional, List
import secrets
from datetime import datetime, timedelta
from helpers.device_info import get_device_info
from database.connection import get_db_connection
import sqlite3

# تخزين الجلسات في الذاكرة
sessions_cache: Dict[str, dict] = {}


class TokenHandler:
    @staticmethod
    def generate_token() -> str:
        """إنشاء توكن عشوائي آمن"""
        return secrets.token_hex(32)

    @staticmethod
    def create_session(user_id: int, user_type: int, request: Request = None) -> str:
        """إنشاء جلسة جديدة مع معلومات المستخدم والجهاز"""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # جلب بيانات المستخدم
            cursor.execute(
                """SELECT first_name, last_name, status 
                FROM users WHERE id = ?""",
                (user_id,)
            )
            user_data = cursor.fetchone()

            if not user_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="المستخدم غير موجود"
                )

            if user_data[2] == 'banned':
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="حسابك محظور ولا يمكنك تسجيل الدخول"
                )

            first_name, last_name, _ = user_data

            # جمع معلومات الجهاز
            device_info = get_device_info(request) if request else {}

            # إنشاء التوكن
            token = TokenHandler.generate_token()
            expires_at = datetime.now() + timedelta(hours=24)

            sessions_cache[token] = {
                "user_id": user_id,
                "user_type": user_type,
                "expires_at": expires_at,
                "created_at": datetime.now(),
                "device_info": device_info
            }

            # تخزين في قاعدة البيانات
            cursor.execute(
                """INSERT INTO user_devices 
                (user_id, ip_address, device_name, 
                 device_type, os, browser, country, city)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    device_info.get("ip_address", "unknown"),
                    device_info.get("device_name", "unknown"),
                    device_info.get("device_type", "unknown"),
                    device_info.get("os", "unknown"),
                    device_info.get("browser", "unknown"),
                    device_info.get("country", "unknown"),
                    device_info.get("city", "unknown")
                )
            )
            conn.commit()

            return token

        except sqlite3.Error as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"خطأ في قاعدة البيانات: {str(e)}"
            )
        finally:
            if conn:
                conn.close()


    @staticmethod
    def get_all_sessions() -> List[dict]:
        """الحصول على جميع الجلسات النشطة (للمدير)"""
        active_sessions = []
        for token, session in sessions_cache.items():
            if datetime.now() < session["expires_at"]:
                active_sessions.append({
                    "token": token,
                    "user_id": session["user_id"],
                    "user_type": session["user_type"],
                    "login_time": session["created_at"],
                    "device_info": session.get("device_info", {})
                })
        return active_sessions

    @staticmethod
    def validate_token(token: str) -> Optional[dict]:
        """التحقق من صحة التوكن مع تحديث معلومات النشاط"""
        if token not in sessions_cache:
            return None

        session = sessions_cache[token]

        # التحقق من انتهاء الصلاحية
        if datetime.now() > session["expires_at"]:
            del sessions_cache[token]
            return None

        # التحقق من حالة المستخدم في قاعدة البيانات
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
                del sessions_cache[token]
                return None

        except Exception as e:
            print(f"Error validating token: {str(e)}")
            del sessions_cache[token]
            return None
        finally:
            if conn:
                conn.close()

        return session

    @staticmethod
    def delete_session(token: str):
        """حذف جلسة المستخدم"""
        if token in sessions_cache:
            del sessions_cache[token]

    @staticmethod
    def delete_all_user_sessions(user_id: int):
        """حذف جميع جلسات المستخدم"""
        global sessions_cache
        sessions_cache = {
            t: s for t, s in sessions_cache.items()
            if s["user_id"] != user_id
        }

    @staticmethod
    def get_user_sessions(user_id: int) -> list:
        """الحصول على جميع جلسات المستخدم النشطة"""
        return [
            {"token": t, **s}
            for t, s in sessions_cache.items()
            if s["user_id"] == user_id
        ]


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

        # تحديث معلومات النشاط الأخير
        session["last_activity"] = datetime.now()
        session["token"] = credentials.credentials

        return session


class AdminTokenHandler(HTTPBearer):
    """مخصص للتحقق من توكن المدير"""

    async def __call__(self, request: Request) -> dict:
        credentials = await super().__call__(request)
        session = TokenHandler.validate_token(credentials.credentials)

        if not session or session["user_type"] != 1:  # 1 = مدير
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="صلاحية غير كافية"
            )

        return session


admin_scheme = AdminTokenHandler()

auth_scheme = JWTBearer()
