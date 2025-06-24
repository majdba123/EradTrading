import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status
from database.connection import get_db_connection
from schemas.users import UserLogin, UserRegister, TokenResponse
from auth import TokenHandler, auth_scheme
from helpers.otp_helper import OTPHelper
from helpers.otp_session import otp_session_manager
from fastapi import Request
from helpers.device_info import get_device_info

router = APIRouter(tags=["Authentication"])

# كلمة المرور الثابتة لجميع المستخدمين
FIXED_PASSCODE = "123456"


@router.post("/register", response_model=TokenResponse, summary="Create new account")
async def register(user: UserRegister, request: Request):
    """
    Register a new user account (requires admin approval):
    - **phone**: Phone number (must be unique)
    - **first_name**: First name
    - **last_name**: Last name
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if user already exists
        cursor.execute(
            "SELECT id FROM users WHERE phone = ?",
            (user.phone,)
        )
        existing_user = cursor.fetchone()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered"
            )

        # Create new account with fixed password and 'pending_approval' status
        cursor.execute(
            """INSERT INTO users 
            (phone, passcode, first_name, last_name, type, status) 
            VALUES (?, ?, ?, ?, ?, ?)""",
            (user.phone, FIXED_PASSCODE, user.first_name,
             user.last_name, 0, 'pending_approval')
        )
        user_id = cursor.lastrowid
        conn.commit()

        # Delete any old OTP sessions
        otp_session_manager.delete_user_sessions(user_id)

        # Send OTP
        session_id = OTPHelper.send_and_store_otp(user_id, user.phone)

        token = TokenHandler.create_session(user_id, 0, request)

        return {
            "access_token": token,
            "message": "Account created successfully. Waiting for admin approval. OTP verification code sent.",
            "user_type": 0,
            "otp_required": True,
            "status": "pending_approval"
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/login", response_model=TokenResponse, summary="User login")
async def login(user: UserLogin, request: Request):
    """
    Login to existing account:
    - **phone**: Registered phone number
    - **passcode**: Will be ignored (using fixed passcode)
    """
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Phone number not registered"
            )

        user_id, stored_passcode, user_status, user_type = user_data

        if FIXED_PASSCODE != stored_passcode:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        if user_status == 'pending_approval':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is pending admin approval"
            )

        if user_status == 'rejected':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been rejected"
            )

        if user_status == 'banned':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been banned"
            )

        # Delete any old OTP sessions
        otp_session_manager.delete_user_sessions(user_id)

        # Send OTP
        session_id = OTPHelper.send_and_store_otp(user_id, user.phone)

        token = TokenHandler.create_session(user_id, user_type, request)

        return {
            "access_token": token,
            "message": "OTP verification code sent",
            "user_type": user_type,
            "otp_required": True
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/verify-otp", summary="تحقق من رمز OTP")
async def verify_otp(otp: str, user_data: dict = Depends(auth_scheme)):
    """
    التحقق من رمز OTP المرسل إلى المستخدم:
    - **otp**: رمز التحقق الذي استلمه المستخدم (مطلوب)
    """
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


@router.post("/logout", summary="تسجيل الخروج")
async def logout(user_data: dict = Depends(auth_scheme)):
    """
    تسجيل خروج المستخدم وإنهاء الجلسة الحالية
    """
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


@router.get("/check-auth", summary="فحص حالة المصادقة")
async def check_auth(user_data: dict = Depends(auth_scheme)):
    """
    فحص ما إذا كان المستخدم مصادقًا عليه أم لا
    """
    return {
        "authenticated": True,
        "user_id": user_data["user_id"],
        "user_type": user_data["user_type"]
    }


@router.get("/devices", summary="الحصول على أجهزة المستخدم")
async def get_user_devices(user_data: dict = Depends(auth_scheme)):
    """الحصول على سجل أجهزة المستخدم"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT ip_address, device_name, device_type, os, browser, country, city, login_time 
               FROM user_devices 
               WHERE user_id = ?
               ORDER BY login_time DESC""",
            (user_data["user_id"],)
        )

        devices = []
        for row in cursor.fetchall():
            devices.append({
                "ip_address": row[0],
                "device_name": row[1],
                "device_type": row[2],
                "os": row[3],
                "browser": row[4],
                "country": row[5],
                "city": row[6],
                "login_time": row[7]
            })

        return {
            "success": True,
            "devices": devices
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"فشل في جلب بيانات الأجهزة: {str(e)}"
        )
    finally:
        if conn:
            conn.close()
