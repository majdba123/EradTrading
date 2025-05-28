from fastapi import APIRouter, Depends, HTTPException, status
from database.connection import get_db_connection
from schemas.mt5 import (
    MT5AccountCreate,
    MT5AccountInfo,
    MT5DepositWithdraw,
    MT5Transfer,
    MT5PasswordChange
)
from auth import auth_scheme
from admin_auth import admin_scheme
from SCBClient import SCBClient, SCBAPIError, AuthenticationError
from security import cipher
import sqlite3

router = APIRouter(
    prefix="/mt5",
    tags=["Admin MT5 Management"]
)

# إعادة استخدام إعدادات MT5 من الملف الأصلي
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


@router.post("/accounts/{user_id}", response_model=dict, summary="Create MT5 account for user")
async def admin_create_mt5_account(
    user_id: int,
    account_data: dict,
    admin_data: dict = Depends(admin_scheme)
):
    """
    إنشاء حساب MT5 للمستخدم (للمدير فقط)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # التحقق من وجود المستخدم
        cursor.execute(
            "SELECT first_name, last_name FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        first_name, last_name = user

        # إنشاء الحساب في MT5
        client = get_mt5_client()
        result = client.create_account(
            first_name=first_name,
            last_name=last_name,
            account_type=account_data["account_type"]
        )

        # تشفير كلمات المرور
        encrypted_password = cipher.encrypt_password(result["password"])
        encrypted_investor_password = cipher.encrypt_password(
            result["investor_password"])

        # تخزين بيانات الحساب
        cursor.execute(
            """INSERT INTO user_mt5_accounts 
            (user_id, mt5_login_id, mt5_password, mt5_investor_password, account_type) 
            VALUES (?, ?, ?, ?, ?)""",
            (
                user_id,
                result["login"],
                encrypted_password,
                encrypted_investor_password,
                result["type"]
            )
        )
        conn.commit()

        return {
            "success": True,
            "message": "MT5 account created successfully for user",
            "user_id": user_id,
            "account_details": {
                "login": result["login"],
                "password": result["password"],
                "investor_password": result["investor_password"],
                "type": result["type"]
            }
        }

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400,
            detail="User already has an MT5 account"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.get("/accounts/{user_id}", response_model=list, summary="Get user's MT5 accounts")
async def admin_get_user_accounts(
    user_id: int,
    admin_data: dict = Depends(admin_scheme)
):
    """
    الحصول على جميع حسابات MT5 الخاصة بالمستخدم (للمدير فقط)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT mt5_login_id, mt5_password, mt5_investor_password, 
                  account_type, created_at 
            FROM user_mt5_accounts 
            WHERE user_id = ?""",
            (user_id,)
        )
        accounts = cursor.fetchall()

        result = []
        for account in accounts:
            try:
                result.append({
                    "login": account[0],
                    "password": cipher.decrypt_password(account[1]) if account[1] else None,
                    "investor_password": cipher.decrypt_password(account[2]) if account[2] else None,
                    "type": account[3],
                    "created_at": account[4]
                })
            except:
                result.append({
                    "login": account[0],
                    "password": "******",
                    "investor_password": "******",
                    "type": account[3],
                    "created_at": account[4],
                    "decryption_error": True
                })

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/accounts/deposit/{user_id}/{login}", summary="Deposit to user's MT5 account")
async def admin_deposit_to_mt5(
    user_id: int,
    login: int,
    transaction: MT5DepositWithdraw,
    admin_data: dict = Depends(admin_scheme)
):
    """
    إيداع أموال في حساب MT5 للمستخدم (للمدير فقط)
    """
    # التحقق من أن الحساب يخص المستخدم
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM user_mt5_accounts WHERE user_id = ? AND mt5_login_id = ?",
            (user_id, login)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="This account does not belong to the specified user"
            )

        # تنفيذ الإيداع
        client = get_mt5_client()
        result = client.deposit(
            login=login,
            amount=transaction.amount,
            comment=f"Admin deposit: {transaction.comment or 'No comment'}"
        )

        return {
            "success": True,
            "message": "Deposit successful",
            "user_id": user_id,
            "login": login,
            "transaction_details": result
        }

    except SCBAPIError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Deposit failed: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/accounts/withdraw/{user_id}/{login}", summary="Withdraw from user's MT5 account")
async def admin_withdraw_from_mt5(
    user_id: int,
    login: int,
    transaction: MT5DepositWithdraw,
    admin_data: dict = Depends(admin_scheme)
):
    """
    سحب أموال من حساب MT5 للمستخدم (للمدير فقط)
    """
    # التحقق من أن الحساب يخص المستخدم
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM user_mt5_accounts WHERE user_id = ? AND mt5_login_id = ?",
            (user_id, login)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="This account does not belong to the specified user"
            )

        # تنفيذ السحب
        client = get_mt5_client()
        result = client.withdraw(
            login=login,
            amount=transaction.amount,
            comment=f"Admin withdrawal: {transaction.comment or 'No comment'}"
        )

        return {
            "success": True,
            "message": "Withdrawal successful",
            "user_id": user_id,
            "login": login,
            "transaction_details": result
        }

    except SCBAPIError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Withdrawal failed: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/accounts/transfer/{user_id}", summary="Transfer between user's accounts")
async def admin_transfer_between_mt5(
    user_id: int,
    transfer: MT5Transfer,
    admin_data: dict = Depends(admin_scheme)
):
    """
    تحويل أموال بين حسابات MT5 للمستخدم (للمدير فقط)
    """
    # التحقق من أن الحسابات تخص المستخدم
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # التحقق من الحساب المرسل
        cursor.execute(
            "SELECT 1 FROM user_mt5_accounts WHERE user_id = ? AND mt5_login_id = ?",
            (user_id, transfer.from_login)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="Source account does not belong to the specified user"
            )

        # التحقق من الحساب المستقبل
        cursor.execute(
            "SELECT 1 FROM user_mt5_accounts WHERE user_id = ? AND mt5_login_id = ?",
            (user_id, transfer.to_login)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="Destination account does not belong to the specified user"
            )

        # تنفيذ التحويل
        client = get_mt5_client()
        result = client.transfer(
            from_login=transfer.from_login,
            to_login=transfer.to_login,
            amount=transfer.amount
        )

        return {
            "success": True,
            "message": "Transfer successful",
            "user_id": user_id,
            "transaction_details": result
        }

    except SCBAPIError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Transfer failed: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/accounts/change-password/{user_id}/{login}", summary="Change MT5 account password")
async def admin_change_mt5_password(
    user_id: int,
    login: int,
    password_data: MT5PasswordChange,
    admin_data: dict = Depends(admin_scheme)
):
    """
    تغيير كلمة مرور حساب MT5 للمستخدم (للمدير فقط)
    """
    conn = None
    try:
        # التحقق من أن الحساب يخص المستخدم
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM user_mt5_accounts WHERE user_id = ? AND mt5_login_id = ?",
            (user_id, login)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="This account does not belong to the specified user"
            )

        # تغيير كلمة المرور في MT5
        client = get_mt5_client()
        new_password = client.generate_password(8)

        success = client.change_password(
            login=login,
            new_password=new_password,
            password_type=password_data.password_type
        )

        if not success:
            raise HTTPException(
                status_code=400,
                detail="MT5 password change failed"
            )

        # تحديث كلمة المرور في قاعدة البيانات
        encrypted_password = cipher.encrypt_password(new_password)

        if password_data.password_type == "MAIN":
            cursor.execute(
                "UPDATE user_mt5_accounts SET mt5_password = ? WHERE user_id = ? AND mt5_login_id = ?",
                (encrypted_password, user_id, login)
            )
        else:  # INVESTOR
            cursor.execute(
                "UPDATE user_mt5_accounts SET mt5_investor_password = ? WHERE user_id = ? AND mt5_login_id = ?",
                (encrypted_password, user_id, login)
            )

        conn.commit()

        return {
            "success": True,
            "message": "Password changed successfully",
            "user_id": user_id,
            "login": login,
            "password_type": password_data.password_type,
            "new_password": new_password  # إرجاع كلمة المرور الجديدة للمدير
        }

    except SCBAPIError as e:
        raise HTTPException(
            status_code=400,
            detail=f"MT5 password change failed: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/accounts/enable-trading/{user_id}/{login}", summary="Enable trading for user's account")
async def admin_enable_mt5_trading(
    user_id: int,
    login: int,
    admin_data: dict = Depends(admin_scheme)
):
    """
    تمكين التداول لحساب MT5 للمستخدم (للمدير فقط)
    """
    conn = None
    try:
        # التحقق من أن الحساب يخص المستخدم
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM user_mt5_accounts WHERE user_id = ? AND mt5_login_id = ?",
            (user_id, login)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="This account does not belong to the specified user"
            )

        # تمكين التداول
        client = get_mt5_client()
        result = client.enable_trading(login)

        return {
            "success": True,
            "message": "Trading enabled successfully",
            "user_id": user_id,
            "login": login,
            "account_info": result
        }

    except SCBAPIError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to enable trading: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/accounts/update-rights/{user_id}/{login_id}",
             response_model=dict,
             summary="Update MT5 account permissions (Admin)")
async def admin_update_mt5_user_rights(
    user_id: int,
    login_id: int,
    rights_data: dict,
    admin_data: dict = Depends(admin_scheme)
):
    """
    تحديث صلاحيات وإعدادات حساب MT5 (للمدير فقط)

    المطلوب:
    - Path Parameters:
        - user_id: معرف المستخدم المالك للحساب
        - login_id: رقم حساب MT5
    - Request Body:
    {
        "rights": {
            "USER_RIGHT_ENABLED": 1,       // 1 لتمكين، 0 لتعطيل
            "USER_RIGHT_TRADE_DISABLED": 0  // 1 لتعطيل التداول، 0 لتمكين
        },
        "params": {                        // اختياري
            "leverage": 100,               // الرافعة المالية
            "email": "user@example.com"    // البريد الإلكتروني
        }
    }
    """
    conn = None
    try:
        # 1. التحقق من أن الحساب يخص المستخدم المحدد
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT 1 FROM user_mt5_accounts 
               WHERE user_id = ? AND mt5_login_id = ?""",
            (user_id, login_id)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="الحساب لا ينتمي للمستخدم المحدد"
            )

        # 2. التحقق من وجود البيانات المطلوبة
        if not rights_data.get("rights"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="يجب تقديم بيانات الصلاحيات المطلوبة"
            )

        rights = rights_data["rights"]
        params = rights_data.get("params", {})

        # 3. تحديث الصلاحيات في MT5
        client = get_mt5_client()
        result = client.update_user_rights(
            login=login_id,
            rights=rights,
            params=params
        )

        # 4. إرجاع النتيجة
        return {
            "success": True,
            "message": "تم تحديث صلاحيات الحساب بنجاح",
            "user_id": user_id,
            "login_id": login_id,
            "updated_rights": rights,
            "updated_params": params,
            "mt5_response": result
        }

    except HTTPException:
        raise
    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"خطأ في تحديث الصلاحيات: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"حدث خطأ غير متوقع: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/accounts/disable-trading/{user_id}/{login}", summary="Disable trading for user's account")
async def admin_disable_mt5_trading(
    user_id: int,
    login: int,
    admin_data: dict = Depends(admin_scheme)
):
    """
    تعطيل التداول لحساب MT5 للمستخدم (للمدير فقط)
    """
    conn = None
    try:
        # التحقق من أن الحساب يخص المستخدم
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM user_mt5_accounts WHERE user_id = ? AND mt5_login_id = ?",
            (user_id, login)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=403,
                detail="This account does not belong to the specified user"
            )

        # تعطيل التداول
        client = get_mt5_client()
        result = client.disable_trading(login)

        return {
            "success": True,
            "message": "Trading disabled successfully",
            "user_id": user_id,
            "login": login,
            "account_info": result
        }

    except SCBAPIError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to disable trading: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        if conn:
            conn.close()
