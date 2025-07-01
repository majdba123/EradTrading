import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status
from database.connection import get_db_connection
from schemas.users import UserLogin, UserRegister, TokenResponse
from auth import TokenHandler, auth_scheme
from helpers.otp_helper import OTPHelper
from helpers.otp_session import otp_session_manager
from fastapi import Request
from helpers.device_info import get_device_info
from typing import List, Union
from security import cipher  # Import encryption object


router = APIRouter(tags=["Authentication"])

# Fixed password for all users


@router.post("/auth", response_model=TokenResponse, summary="Unified authentication")
async def authenticate(user_data: Union[UserLogin, UserRegister], request: Request):
    """
    Unified authentication endpoint:
    - If phone exists: Verify credentials and login
    - If phone doesn't exist: Register new account

    For login (existing users):
    - **phone**: Registered phone number
    - **password**: User's password

    For registration (new users):
    - **phone**: Phone number (must be unique)
    - **first_name**: First name
    - **last_name**: Last name
    - **password**: User's password
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute(
            "SELECT id, password, status, type FROM users WHERE phone = ?",
            (user_data.phone,)
        )
        existing_user = cursor.fetchone()

        if existing_user:
            # LOGIN FLOW
            user_id, stored_password, user_status, user_type = existing_user

            # Verify password
            encrypted_password = cipher.decrypt_password(stored_password)
            if not user_data.password == encrypted_password:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )

            # Check account status
            if user_status == 'pending_approval':
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your account is pending admin approval"
                )
            elif user_status == 'rejected':
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your account has been rejected"
                )
            elif user_status == 'banned':
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your account has been banned"
                )

        else:
            # REGISTRATION FLOW
            if not hasattr(user_data, 'first_name') or not hasattr(user_data, 'last_name'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="First name and last name are required for registration"
                )

            encrypted_password = cipher.encrypt_password(user_data.password)

            # Create new account with fixed passcode and 'pending_approval' status
            cursor.execute(
                """INSERT INTO users 
                (phone, passcode, first_name, last_name, type, status, password) 
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_data.phone, user_data.passcode, user_data.first_name,
                 user_data.last_name, 0, 'pending_approval', encrypted_password)
            )
            user_id = cursor.lastrowid
            user_type = 0
            user_status = 'pending_approval'
            conn.commit()

        # Common flow for both registration and login
        otp_session_manager.delete_user_sessions(user_id)
        session_id = OTPHelper.send_and_store_otp(user_id, user_data.phone)
        token = TokenHandler.create_session(user_id, user_type, request)

        return {
            "access_token": token,
            "message": "OTP verification code sent",
            "user_type": user_type,
            "otp_required": True,
            "status": user_status,
            "is_new_user": not bool(existing_user)
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/verify-otp", summary="Verify OTP code")
async def verify_otp(otp: str, user_data: dict = Depends(auth_scheme)):
    """
    Verify the OTP code sent to the user:
    - **otp**: The verification code received by the user (required)
    """
    try:
        user_id = user_data["user_id"]

        if not OTPHelper.verify_otp_for_user(user_id, otp):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OTP code"
            )

        return {
            "success": True,
            "message": "OTP verified successfully",
            "user_id": user_id
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OTP verification failed: {str(e)}"
        )


@router.post("/logout", summary="User logout")
async def logout(user_data: dict = Depends(auth_scheme)):
    """
    Logout the user and terminate the current session
    """
    try:
        token = user_data["token"]
        user_id = user_data["user_id"]

        # Delete the user's OTP session
        otp_session_manager.delete_user_sessions(user_id)

        # Delete the token session
        TokenHandler.delete_session(token)

        return {
            "success": True,
            "message": "Logout successful",
            "user_id": user_id
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Logout failed: {str(e)}"
        )


@router.get("/check-auth", summary="Check authentication status")
async def check_auth(user_data: dict = Depends(auth_scheme)):
    """
    Check if the user is authenticated or not
    """
    return {
        "authenticated": True,
        "user_id": user_data["user_id"],
        "user_type": user_data["user_type"]
    }


@router.get("/devices", summary="Get user devices")
async def get_user_devices(user_data: dict = Depends(auth_scheme)):
    """Retrieve the user's device history"""
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
            detail=f"Failed to retrieve device data: {str(e)}"
        )
    finally:
        if conn:
            conn.close()
