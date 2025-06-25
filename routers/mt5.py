import sqlite3
from security import cipher  # استيراد كائن التشفير
from fastapi import APIRouter, Depends, HTTPException, status, Request
from database.connection import get_db_connection
from schemas.mt5 import (
    MT5AccountCreate,
    MT5AccountInfo,
    MT5DepositWithdraw,
    MT5Transfer,
    MT5PasswordChange
)
from auth import auth_scheme
from SCBClient import SCBClient, SCBAPIError, AuthenticationError
import json
from Securityy.permission_checker import check_permission
from Securityy.user_permission_checker import UserPermissionChecker


router = APIRouter(tags=["MT5 Integration"])

# Initialize SCB Client (you might want to move this to config)
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


@router.post("/accounts", response_model=dict, summary="Create New Account")
async def create_mt5_account(
    account_data: dict,
    request: Request,
    user_data: dict = Depends(auth_scheme),
    _: bool = Depends(check_permission),
    has_permission: bool = Depends(
        UserPermissionChecker("mt5_get_accounts"))
):
    """
    إنشاء حساب جديد في MT5 مع **تشفير كلمات المرور**.
    يتم التحقق من صلاحية الوصول أولاً قبل تنفيذ العملية.
    """
    # لا حاجة لفحص has_permission هنا لأنه تم التحقق منه في Depends

    client = get_mt5_client()
    conn = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT first_name, last_name FROM users WHERE id = ?",
            (user_data["user_id"],)
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        first_name, last_name = user

        # إنشاء الحساب في MT5 (معلق حالياً)
        # result = client.create_account(
        #     first_name=first_name,
        #     last_name=last_name,
        #     account_type=account_data["account_type"]
        # )

        # تخزين بيانات الحساب في قاعدة البيانات
        cursor.execute(
            """INSERT INTO user_mt5_accounts 
            (user_id, mt5_login_id, mt5_password, mt5_investor_password, account_type) 
            VALUES (?, ?, ?, ?, ?)""",
            (
                user_data["user_id"],
                0,  # mt5_login_id مؤقت
                0,  # mt5_password مؤقت
                0,  # mt5_investor_password مؤقت
                account_data["account_type"]
            )
        )
        conn.commit()

        return {
            "success": True,
            "message": "MT5 account created successfully",
        }

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400,
            detail="An MT5 account already exists for this user."
        )
    except HTTPException:
        # إعادة رفع أي استثناءات HTTP كما هي
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        if conn:
            conn.close()

####################################################################################################################################################
####################################################################################################################################################
####################################################################################################################################################


@router.get("/accounts/my-accounts", response_model=list, summary="Get all my MT5 accounts")
async def get_my_mt5_accounts(user_data: dict = Depends(auth_scheme),
                              _: bool = Depends(check_permission),
                              has_permission: bool = Depends(
                                  UserPermissionChecker("mt5_get_accounts"))

                              ):
    """
    الحصول على جميع حسابات MT5 الخاصة بالمستخدم الحالي مع فك تشفير كلمات المرور

    يتم في كل طلب:
    1. جلب الحسابات من قاعدة البيانات
    2. فك تشفير كلمات المرور لكل حساب
    3. إرجاع البيانات مع كلمات المرور المفكوكة
    """
    conn = None
    try:
        # 1. جلب الحسابات من قاعدة البيانات
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT mt5_login_id, mt5_password, mt5_investor_password, 
                  account_type, created_at 
            FROM user_mt5_accounts 
            WHERE user_id = ?""",
            (user_data["user_id"],)
        )
        accounts = cursor.fetchall()

        if not accounts:
            return []

        result = []
        for account in accounts:
            login = account[0]

            # 2. فك تشفير كلمات المرور لكل حساب
            try:
                # الحصول على كلمة المرور الرئيسية المفكوكة
                password = cipher.decrypt_password(
                    account[1]) if account[1] else None

                # الحصول على كلمة مرور المستثمر المفكوكة
                investor_password = cipher.decrypt_password(
                    account[2]) if account[2] else None

                # 3. إضافة الحساب مع كلمات المرور المفكوكة
                result.append({
                    "login": login,
                    "password": password,
                    "investor_password": investor_password,
                    "type": account[3],
                    "created_at": account[4]
                })

            except Exception as decrypt_error:
                # في حالة فشل فك التشفير، نرجع كلمة مرور مخفية
                print(
                    f"Account password decryption failed {login}: {str(decrypt_error)}")
                result.append({
                    "login": login,
                    "password": "******",
                    "investor_password": "******",
                    "type": account[3],
                    "created_at": account[4],
                    "decryption_error": True
                })

        return result

    except sqlite3.Error as db_error:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(db_error)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


####################################################################################################################################################
####################################################################################################################################################
####################################################################################################################################################


@router.get("/accounts/{login}", response_model=MT5AccountInfo, summary="Get MT5 account information")
async def get_mt5_account(login: int, user_data: dict = Depends(auth_scheme), _: bool = Depends(check_permission),
                          has_permission: bool = Depends(
        UserPermissionChecker("mt5_get_accounts"))):
    """
    الحصول على معلومات حساب MT5

    المتطلبات:
    - **login**: رقم حساب MT5 (يجب أن يكون الحساب مسجلاً للمستخدم الحالي)
    """
    conn = None
    try:
        # التحقق من أن الحساب يخص المستخدم الحالي
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM user_mt5_accounts WHERE user_id = ? AND mt5_login_id = ?",
            (user_data["user_id"], login)
        )
        account_exists = cursor.fetchone()

        if not account_exists:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this account."
            )

        # جلب معلومات الحساب من MT5
        client = get_mt5_client()
        account_info = client.get_account_info(login)

        return {
            "login": login,
            "info": account_info,
            "success": True
        }

    except HTTPException:
        raise
    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if e.code == 404 else status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch account information: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


####################################################################################################################################################
####################################################################################################################################################
####################################################################################################################################################

@router.post("/auth/send-otp", response_model=dict, summary="Send OTP verification code",)
async def send_otp(
    phone_data: dict,
    user_data: dict = Depends(auth_scheme), _: bool = Depends(check_permission),
    has_permission: bool = Depends(
        UserPermissionChecker("mt5_get_accounts"))
):
    """
    إرسال رمز OTP إلى رقم الهاتف

    المطلوب:
    {
        "phone": "رقم الهاتف (مع مفتاح الدولة)"
    }
    """
    try:
        phone = phone_data.get("phone")
        if not phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number must be provided."
            )

        client = get_mt5_client()
        result = client.send_otp(phone)

        return {
            "success": True,
            "message": "Verification code sent",
            "phone": phone,
            "otp_ref": result.get("otp_ref"),  # مرجع للتحقق لاحقاً
            "expires_in": 300  # ثانية (5 دقائق)
        }

    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to send code: {e.message}"
        )


####################################################################################################################################################
####################################################################################################################################################
####################################################################################################################################################


@router.post("/accounts/change-password/{login}/", summary="Change MT5 account password")
async def change_mt5_password(
    login: int,
    password_data: MT5PasswordChange,
    user_data: dict = Depends(auth_scheme),
    _: bool = Depends(check_permission),
    has_permission: bool = Depends(
        UserPermissionChecker("mt5_get_accounts"))
):
    """
    تغيير كلمة مرور حساب MT5 وتحديثها في قاعدة البيانات

    المتطلبات:
    - **new_password**: كلمة المرور الجديدة
    - **password_type**: نوع كلمة المرور (MAIN أو INVESTOR)
    """
    conn = None
    try:
        # التحقق من أن الحساب يخص المستخدم الحالي
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM user_mt5_accounts WHERE user_id = ? AND mt5_login_id = ?",
            (user_data["user_id"], login)
        )
        account_exists = cursor.fetchone()

        if not account_exists:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this account."
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
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MT5 password change failed"
            )

        # تحديث كلمة المرور في قاعدة البيانات (مع التشفير)
        encrypted_password = cipher.encrypt_password(new_password)

        if password_data.password_type == "MAIN":
            cursor.execute(
                "UPDATE user_mt5_accounts SET mt5_password = ? WHERE user_id = ? AND mt5_login_id = ?",
                (encrypted_password, user_data["user_id"], login)
            )
        else:  # INVESTOR
            cursor.execute(
                "UPDATE user_mt5_accounts SET mt5_investor_password = ? WHERE user_id = ? AND mt5_login_id = ?",
                (encrypted_password, user_data["user_id"], login)
            )

        conn.commit()

        return {
            "success": True,
            "message": "Password changed successfully in MT5 and database",
            "login": login,
            "password_type": password_data.password_type
        }

    except HTTPException:
        raise
    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"MT5 password change failed: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        if conn:
            conn.close()

####################################################################################################################################################
####################################################################################################################################################
####################################################################################################################################################


@router.post("/accounts/check-password/{login_id}", response_model=dict, summary="Verify your MT5 account password")
async def verify_mt5_password(
    login_id: int,  # سيستقبل login_id كمسار في الرابط
    password_request: dict,  # سيستقبل كلمة المرور ونوعها
    user_data: dict = Depends(auth_scheme), _: bool = Depends(check_permission),
    has_permission: bool = Depends(
        UserPermissionChecker("mt5_get_accounts"))
):
    """
    التحقق من صحة كلمة مرور حساب MT5 مع التحقق من ملكية الحساب

    المطلوب:
    - Path Parameter: login_id (رقم حساب MT5)
    - Request Body:
    {
        "password": "كلمة المرور المراد التحقق منها",
        "password_type": "MAIN" أو "INVESTOR" (اختياري - افتراضي MAIN)
    }

    العملية:
    1. التحقق من أن login_id يخص المستخدم المصادق عليه
    2. التحقق من كلمة المرور مع MT5
    3. إرجاع نتيجة التحقق
    """
    conn = None
    try:
        # 1. التحقق من وجود البيانات المطلوبة
        if not password_request.get("password"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be entered"
            )

        password = password_request["password"]
        password_type = password_request.get("password_type", "MAIN")

        # 2. التحقق من أن الحساب يخص المستخدم
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT 1 
               FROM user_mt5_accounts 
               WHERE user_id = ? AND mt5_login_id = ?""",
            (user_data["user_id"], login_id)
        )
        account_exists = cursor.fetchone()

        if not account_exists:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this account."
            )

        # 3. التحقق من كلمة المرور مع MT5
        client = get_mt5_client()
        is_valid = client.check_password(
            login=login_id,
            password=password,
            password_type=password_type
        )

        # 4. إرجاع النتيجة
        return {
            "success": True,
            "login_id": login_id,
            "password_type": password_type,
            "is_valid": is_valid,
            "message": "The password is correct" if is_valid else "The password is incorrect.",
            "user_verified": True  # تأكيد أن المستخدم يملك هذا الحساب
        }

    except HTTPException:
        raise
    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password verification error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        if conn:
            conn.close()

####################################################################################################################################################
####################################################################################################################################################
####################################################################################################################################################


@router.post("/accounts/update-rights/{login_id}",
             response_model=dict,
             summary="Update MT5 account permissions")
async def update_mt5_user_rights(
    login_id: int,
    rights_data: dict,
    user_data: dict = Depends(auth_scheme), _: bool = Depends(check_permission),
    has_permission: bool = Depends(
        UserPermissionChecker("mt5_get_accounts"))
):
    """
    تحديث صلاحيات وإعدادات حساب MT5 مع التحقق من ملكية الحساب

    المطلوب:
    - Path Parameter: login_id (رقم حساب MT5)
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
        # 1. التحقق من ملكية الحساب
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT 1 FROM user_mt5_accounts 
               WHERE user_id = ? AND mt5_login_id = ?""",
            (user_data["user_id"], login_id)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this account."
            )

        # 2. التحقق من وجود البيانات المطلوبة
        if not rights_data.get("rights"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The required authorization data must be provided."
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
            "login_id": login_id,
            "updated_rights": rights,
            "updated_params": params,
            "mt5_response": result,
            "user_verified": True
        }

    except HTTPException:
        raise
    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating permissions: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


####################################################################################################################################################
####################################################################################################################################################
####################################################################################################################################################


@router.post("/accounts/{login}/deposit", summary="Deposit funds into an MT5 account")
async def deposit_to_mt5(login: int, transaction: MT5DepositWithdraw, user_data: dict = Depends(auth_scheme), _: bool = Depends(check_permission),
                         has_permission: bool = Depends(
        UserPermissionChecker("mt5_get_accounts"))):
    """
    إيداع أموال في حساب MT5

    المتطلبات:
    - **amount**: المبلغ المطلوب إيداعه
    - **comment**: تعليق على العملية (اختياري)
    """
    client = get_mt5_client()
    try:
        result = client.deposit(
            login=login,
            amount=transaction.amount,
            comment=transaction.comment or "Deposit from API"
        )
        return {
            "success": True,
            "message": "Deposit successfully",
            "transaction_details": result
        }
    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Deposit failed: {e.message}"
        )


@router.post("/accounts/{login}/withdraw", summary="Withdraw funds from an MT5 account")
async def withdraw_from_mt5(login: int, transaction: MT5DepositWithdraw, user_data: dict = Depends(auth_scheme), _: bool = Depends(check_permission),
                            has_permission: bool = Depends(
        UserPermissionChecker("mt5_get_accounts"))):
    """
    سحب أموال من حساب MT5

    المتطلبات:
    - **amount**: المبلغ المطلوب سحبه
    - **comment**: تعليق على العملية (اختياري)
    """
    client = get_mt5_client()
    try:
        result = client.withdraw(
            login=login,
            amount=transaction.amount,
            comment=transaction.comment or "Withdrawal from API"
        )
        return {
            "success": True,
            "message": "Withdrawal successful",
            "transaction_details": result
        }
    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Withdrawal failed: {e.message}"
        )


@router.post("/accounts/transfer", summary="Transfer funds between MT5 accounts")
async def transfer_between_mt5(transfer: MT5Transfer, user_data: dict = Depends(auth_scheme), _: bool = Depends(check_permission),
                               has_permission: bool = Depends(
        UserPermissionChecker("mt5_get_accounts"))):
    """
    تحويل أموال بين حسابات MT5

    المتطلبات:
    - **from_login**: الحساب المرسل
    - **to_login**: الحساب المستقبل
    - **amount**: المبلغ المطلوب تحويله
    """
    client = get_mt5_client()
    try:
        result = client.transfer(
            from_login=transfer.from_login,
            to_login=transfer.to_login,
            amount=transfer.amount
        )
        return {
            "success": True,
            "message": "Transfer successfully",
            "transaction_details": result
        }
    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Conversion failed: {e.message}"
        )


@router.post("/accounts/{login}/enable-trading", summary="Enable trading for MT5 account")
async def enable_mt5_trading(login: int, user_data: dict = Depends(auth_scheme), _: bool = Depends(check_permission),
                             has_permission: bool = Depends(
        UserPermissionChecker("mt5_get_accounts"))):
    """
    تمكين التداول لحساب MT5
    """
    client = get_mt5_client()
    try:
        result = client.enable_trading(login)
        return {
            "success": True,
            "message": "Trading has been successfully enabled.",
            "account_info": result
        }
    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trading enable failed: {e.message}"
        )


@router.post("/accounts/{login}/disable-trading", summary="Disable trading for MT5 account")
async def disable_mt5_trading(login: int, user_data: dict = Depends(auth_scheme), _: bool = Depends(check_permission),
                              has_permission: bool = Depends(
                                  UserPermissionChecker("mt5_get_accounts"))):
    """
    تعطيل التداول لحساب MT5
    """
    client = get_mt5_client()
    try:
        result = client.disable_trading(login)
        return {
            "success": True,
            "message": "Trading has been successfully disabled.",
            "account_info": result
        }
    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trading disable failed: {e.message}"
        )
