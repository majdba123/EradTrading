import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status
from database.connection import get_db_connection
from schemas.users import UserLogin, TokenResponse
from auth import TokenHandler, auth_scheme
from helpers.otp_helper import OTPHelper
from helpers.otp_session import otp_session_manager

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(user: UserLogin):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, passcode, status, type FROM users WHERE phone = ?",
            (user.phone,)
        )
        user_data = cursor.fetchone()

        if not user_data:
            # إنشاء حساب جديد
            cursor.execute(
                "INSERT INTO users (phone, passcode, type) VALUES (?, ?, ?)",
                (user.phone, user.passcode, 0)
            )
            user_id = cursor.lastrowid
            conn.commit()

            # حذف أي جلسات OTP قديمة للمستخدم (إن وجدت)
            otp_session_manager.delete_user_sessions(user_id)

            # إرسال OTP وتخزينه
            session_id = OTPHelper.send_and_store_otp(user_id, user.phone)

            token = TokenHandler.create_session(user_id, 0)
            return {
                "access_token": token,
                "message": "Account created. OTP sent for verification.",
                "user_type": 0,
                "otp_required": True
            }

        user_id, stored_passcode, status, user_type = user_data

        if user.passcode != stored_passcode:
            return {
                "access_token": "",
                "message": "Incorrect password",
                "user_type": 0,
                "otp_required": False
            }

        # حذف أي جلسات OTP قديمة للمستخدم قبل إنشاء الجديدة
        otp_session_manager.delete_user_sessions(user_id)

        # إرسال OTP وتخزينه للمستخدم الموجود
        session_id = OTPHelper.send_and_store_otp(user_id, user.phone)

        token = TokenHandler.create_session(user_id, user_type)

        if status == 'pending':
            message = "Account pending approval. OTP sent for verification."
        elif status == 'rejected':
            message = "Account rejected"
        else:
            message = "OTP sent for verification"

        return {
            "access_token": token,
            "message": message,
            "user_type": user_type,
            "otp_required": True
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Login failed: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/verify-otp")
def verify_otp(otp: str, user_data: dict = Depends(auth_scheme)):
    try:
        user_id = user_data["user_id"]

        if not OTPHelper.verify_otp_for_user(user_id, otp):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="رمز OTP غير صحيح أو منتهي الصلاحية"
            )

        return {
            "success": True,
            "message": "تم التحقق من OTP بنجاح",
            "user_id": user_id
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"فشل التحقق من OTP: {str(e)}"
        )


@router.post("/logout")
def logout(user_data: dict = Depends(auth_scheme)):
    try:
        token = user_data["token"]
        user_id = user_data["user_id"]

        # حذف جلسة OTP الخاصة بالمستخدم
        otp_session_manager.delete_user_sessions(user_id)

        # حذف جلسة التوكن
        TokenHandler.delete_session(token)

        return {
            "success": True,
            "message": "تم تسجيل الخروج بنجاح",
            "user_id": user_id
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"فشل تسجيل الخروج: {str(e)}"
        )
