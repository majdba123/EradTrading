from .otp_session import otp_session_manager
import requests
from typing import Optional, Dict
from fastapi import HTTPException, status
from SCBClient import SCBClient, SCBAPIError, AuthenticationError
import json
from Securityy.permission_checker import check_permission
from Securityy.user_permission_checker import UserPermissionChecker



SCB_BASE_URL = "https://scb.erad-markets.com"
SCB_ADMIN_USER = "admin"
SCB_ADMIN_PASS = "nani*&H#*$HDJbhdb3746bybHBSHDJG&3gnfjenjkbyfv76G673G4UBBEKBF8"

def get_mt5_client():
        """Helper function to get authenticated MT5 client"""
        client = SCBClient(base_url=SCB_BASE_URL, logger_level="OFF")
        try:
            client.authenticate(SCB_ADMIN_USER, SCB_ADMIN_PASS)
            return client
        except AuthenticationError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to connect to MT5 service: {str(e)}"
            )



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
        try:
                phone = phone_number
                if not phone:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Phone number must be provided."
                )

                client = get_mt5_client()
                result = client.send_otp(phone)
                print(result)
                return {
                    "otp": result.get("otp_ref"),  # مرجع للتحقق لاحقاً
                }
        
        except SCBAPIError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to send code: {e}"
                )




    @staticmethod
    def verify_otp_for_user(user_id: int, otp: str) -> bool:
        """التحقق من OTP للمستخدم المحدد"""
        return otp_session_manager.validate_otp(user_id, otp)

    @staticmethod
    def get_user_otp_session(user_id: int) -> Optional[Dict]:
        """الحصول على جلسة OTP الخاصة بالمستخدم إذا وجدت"""
        return otp_session_manager.get_user_otp_session(user_id)
