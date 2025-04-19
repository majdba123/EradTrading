import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status
from database.connection import get_db_connection
import secrets
from typing import Optional, Dict
from schemas.users import UserLogin, TokenResponse
from auth import TokenHandler, auth_scheme
import requests
from datetime import datetime, timedelta

router = APIRouter()


class OTPSessionManager:
    def __init__(self):
        # في الواقع الفعلي، يمكن استخدام Redis أو أي نظام تخزين مؤقت آخر
        self.sessions = {}

    def create_otp_session(self, user_id: int, otp: str, expires_in: int = 300) -> str:
        """إنشاء جلسة OTP جديدة وإرجاع معرف الجلسة"""
        session_id = secrets.token_hex(16)

        self.sessions[session_id] = {
            'user_id': user_id,
            'otp': otp,
            'expires_at': datetime.now() + timedelta(seconds=expires_in),
            'created_at': datetime.now()
        }

        return session_id

    def validate_otp(self, user_id: int, otp: str) -> bool:
        """التحقق من صحة OTP للمستخدم المحدد"""
        for session_id, session_data in list(self.sessions.items()):
            if session_data['user_id'] == user_id and session_data['otp'] == otp:
                if datetime.now() < session_data['expires_at']:
                    del self.sessions[session_id]
                    return True
                else:
                    del self.sessions[session_id]
        return False

    def get_user_otp_session(self, user_id: int) -> Optional[Dict]:
        """الحصول على جلسة OTP الخاصة بالمستخدم إذا وجدت"""
        for session_id, session_data in self.sessions.items():
            if session_data['user_id'] == user_id and datetime.now() < session_data['expires_at']:
                return {'session_id': session_id, **session_data}
        return None

    def delete_user_sessions(self, user_id: int):
        """حذف جميع جلسات OTP الخاصة بالمستخدم"""
        for session_id, session_data in list(self.sessions.items()):
            if session_data['user_id'] == user_id:
                del self.sessions[session_id]


# إنشاء نسخة واحدة من المدير لاستخدامها في التطبيق
otp_session_manager = OTPSessionManager()
