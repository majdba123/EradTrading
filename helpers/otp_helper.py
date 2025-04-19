from .otp_session import otp_session_manager
import requests
from typing import Optional, Dict
from fastapi import HTTPException, status


class OTPHelper:
    @staticmethod
    def send_and_store_otp(user_id: int, phone_number: str) -> str:
        """
        إرسال OTP وتخزينه في الجلسة
        يُرجع: معرف الجلسة (session_id)
        """
        try:
            # محاولة الحصول على OTP من الخدمة الخارجية
            otp = OTPHelper._get_otp_from_external_service(phone_number)
        except Exception as e:
            # استخدام OTP افتراضي عند فشل الخدمة الخارجية
            print(f"استخدام OTP افتراضي بسبب فشل الخدمة الخارجية: {str(e)}")
            otp = "1234567"

        # تخزين OTP في الجلسة بغض النظر عن مصدره
        session_id = otp_session_manager.create_otp_session(user_id, otp)
        return session_id

    @staticmethod
    def _get_otp_from_external_service(phone_number: str) -> str:
        """الحصول على OTP من الخدمة الخارجية"""
        response = requests.post(
            "https://external-otp-service.com/send",
            json={"phone": phone_number},
            timeout=5
        )
        response.raise_for_status()
        return response.json()['otp']

    @staticmethod
    def verify_otp_for_user(user_id: int, otp: str) -> bool:
        """التحقق من OTP للمستخدم المحدد"""
        return otp_session_manager.validate_otp(user_id, otp)

    @staticmethod
    def get_user_otp_session(user_id: int) -> Optional[Dict]:
        """الحصول على جلسة OTP الخاصة بالمستخدم إذا وجدت"""
        return otp_session_manager.get_user_otp_session(user_id)
