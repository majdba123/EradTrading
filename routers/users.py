import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status
from database.connection import get_db_connection
from schemas.users import UserLogin, UserRegister, TokenResponse
from auth import TokenHandler, auth_scheme
from helpers.otp_helper import OTPHelper
from helpers.otp_session import otp_session_manager

router = APIRouter(tags=["Authentication"])

# كلمة المرور الثابتة لجميع المستخدمين
FIXED_PASSCODE = "123456"

@router.post("/register", response_model=TokenResponse, summary="إنشاء حساب جديد")
async def register(user: UserRegister):
    """
    إنشاء حساب جديد للمستخدم مع المعلومات الأساسية:
    - **phone**: رقم الهاتف (يجب أن يكون فريداً)
    - **passcode**: سيتم تجاهل هذا الحقل وسيتم تعيين كلمة المرور كـ 123456
    - **first_name**: الاسم الأول
    - **last_name**: الاسم الأخير
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # التحقق من وجود المستخدم مسبقاً
        cursor.execute(
            "SELECT id FROM users WHERE phone = ?",
            (user.phone,)
        )
        existing_user = cursor.fetchone()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="رقم الهاتف مسجل بالفعل"
            )

        # إنشاء حساب جديد مع كلمة المرور الثابتة
        cursor.execute(
            """INSERT INTO users 
            (phone, passcode, first_name, last_name, type, status) 
            VALUES (?, ?, ?, ?, ?, ?)""",
            (user.phone, FIXED_PASSCODE, user.first_name, user.last_name, 0, 'pending')
        )
        user_id = cursor.lastrowid
        conn.commit()

        # حذف أي جلسات OTP قديمة للمستخدم
        otp_session_manager.delete_user_sessions(user_id)

        # إرسال OTP وتخزينه
        session_id = OTPHelper.send_and_store_otp(user_id, user.phone)

        token = TokenHandler.create_session(user_id, 0)
        return {
            "access_token": token,
            "message": "تم إنشاء الحساب بنجاح. تم إرسال رمز التحقق OTP",
            "user_type": 0,
            "otp_required": True
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"فشل إنشاء الحساب: {str(e)}"
        )
    finally:
        if conn:
            conn.close()

@router.post("/login", response_model=TokenResponse, summary="تسجيل الدخول")
async def login(user: UserLogin):
    """
    تسجيل الدخول للحساب الموجود:
    - **phone**: رقم الهاتف المسجل
    - **passcode**: سيتم تجاهل هذا الحقل وسيتم التحقق مقابل كلمة المرور الثابتة 123456
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
                detail="رقم الهاتف غير مسجل"
            )

        user_id, stored_passcode, user_status, user_type = user_data
        
        if FIXED_PASSCODE != stored_passcode:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="كلمة المرور غير صحيحة"
            )

        if user_status == 'rejected':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="الحساب مرفوض"
            )

        # حذف أي جلسات OTP قديمة للمستخدم
        otp_session_manager.delete_user_sessions(user_id)

        # إرسال OTP وتخزينه للمستخدم الموجود
        session_id = OTPHelper.send_and_store_otp(user_id, user.phone)

        token = TokenHandler.create_session(user_id, user_type)

        message = "تم إرسال رمز التحقق OTP"
        if user_status == 'pending':
            message = "الحساب قيد الانتظار للموافقة. تم إرسال رمز التحقق OTP"

        return {
            "access_token": token,
            "message": message,
            "user_type": user_type,
            "otp_required": True
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"فشل تسجيل الدخول: {str(e)}"
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