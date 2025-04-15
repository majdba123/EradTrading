import sqlite3
from fastapi import APIRouter
from database.connection import get_db_connection
import secrets
from schemas.users import UserLogin, TokenResponse

router = APIRouter()


def generate_token():
    return secrets.token_hex(16)


@router.post("/login", response_model=TokenResponse)
def login(user: UserLogin):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # البحث عن المستخدم
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
            conn.commit()

            token = generate_token()
            return {
                "access_token": token,
                "message": "Account created. Waiting for approval.",
                "user_type": 0
            }

        user_id, stored_passcode, status, user_type = user_data

        # التحقق من كلمة المرور
        if user.passcode != stored_passcode:
            return {
                "access_token": "",
                "message": "Incorrect password",
                "user_type": 0
            }

        # توليد توكن بغض النظر عن حالة الحساب
        token = generate_token()

        # تحديد الرسالة حسب حالة الحساب
        if status == 'pending':
            message = "Account pending approval"
        elif status == 'rejected':
            message = "Account rejected"
        else:
            message = "Login successful"

        return {
            "access_token": token,
            "message": message,
            "user_type": user_type
        }

    except sqlite3.IntegrityError:
        return {
            "access_token": "",
            "message": "Phone already registered",
            "user_type": 0
        }
    except Exception as e:
        return {
            "access_token": "",
            "message": f"Login failed: {str(e)}",
            "user_type": 0
        }
    finally:
        if conn:
            conn.close()
