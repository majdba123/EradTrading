import sqlite3
from security import cipher  # استيراد كائن التشفير
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
from SCBClient import SCBClient, SCBAPIError, AuthenticationError
import json
         

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


































@router.post("/accounts", response_model=dict, summary="إنشاء حساب MT5 جديد")
async def create_mt5_account(account_data: dict, user_data: dict = Depends(auth_scheme)):
    """
    إنشاء حساب جديد في MT5 مع **تشفير كلمات المرور**.
    """
    client = get_mt5_client()
    conn = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT first_name, last_name FROM users WHERE id = ?", (user_data["user_id"],))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="لم يتم العثور على بيانات المستخدم")

        first_name, last_name = user

        # إنشاء الحساب في MT5
        result = client.create_account(
            first_name=first_name,
            last_name=last_name,
            account_type=account_data["account_type"]
        )

        # **تشفير كلمات المرور قبل التخزين**
        encrypted_password = cipher.encrypt_password(result["password"])
        encrypted_investor_password = cipher.encrypt_password(result["investor_password"])

        # تخزين بيانات الحساب في قاعدة البيانات
        cursor.execute(
            """INSERT INTO user_mt5_accounts 
            (user_id, mt5_login_id, mt5_password, mt5_investor_password, account_type) 
            VALUES (?, ?, ?, ?, ?)""",
            (
                user_data["user_id"],
                result["login"],
                encrypted_password,
                encrypted_investor_password,
                result["type"]
            )
        )
        conn.commit()

        return {
            "success": True,
            "message": "تم إنشاء حساب MT5 بنجاح",
            "account_details": {
                "login": result["login"],
                "password": result["password"],  # إرجاع كلمة المرور الأصلية للعميل
                "investor_password": result["investor_password"],
                "type": result["type"],
                "name": f"{first_name} {last_name}"
            }
        }

    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="حساب MT5 موجود بالفعل لهذا المستخدم")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"حدث خطأ غير متوقع: {str(e)}")
    finally:
        if conn:
            conn.close()
            
            
            
            
####################################################################################################################################################
####################################################################################################################################################
####################################################################################################################################################



@router.get("/accounts/my-accounts", response_model=list, summary="الحصول على جميع حساباتي في MT5")
async def get_my_mt5_accounts(user_data: dict = Depends(auth_scheme)):
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
                password = cipher.decrypt_password(account[1]) if account[1] else None
                
                # الحصول على كلمة مرور المستثمر المفكوكة
                investor_password = cipher.decrypt_password(account[2]) if account[2] else None
                
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
                print(f"فشل فك تشفير كلمة المرور للحساب {login}: {str(decrypt_error)}")
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
            detail=f"خطأ في قاعدة البيانات: {str(db_error)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"حدث خطأ غير متوقع: {str(e)}"
        )
    finally:
        if conn:
            conn.close()
        
            
####################################################################################################################################################
####################################################################################################################################################
####################################################################################################################################################
        
            
            
        
        
        
        
@router.get("/accounts/{login}", response_model=MT5AccountInfo, summary="الحصول على معلومات حساب MT5")
async def get_mt5_account(login: int, user_data: dict = Depends(auth_scheme)):
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
                detail="ليس لديك صلاحية الوصول إلى هذا الحساب"
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
            detail=f"فشل جلب معلومات الحساب: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"حدث خطأ غير متوقع: {str(e)}"
        )
    finally:
        if conn:
            conn.close()
            
            
####################################################################################################################################################
####################################################################################################################################################
####################################################################################################################################################
        
            
            
            
@router.post("/accounts/change-password/{login}/", summary="تغيير كلمة مرور حساب MT5")
async def change_mt5_password(
    login: int, 
    password_data: MT5PasswordChange, 
    user_data: dict = Depends(auth_scheme)
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
                detail="ليس لديك صلاحية الوصول إلى هذا الحساب"
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
                detail="فشل تغيير كلمة المرور في MT5"
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
            "message": "تم تغيير كلمة المرور بنجاح في MT5 وقاعدة البيانات",
            "login": login,
            "password_type": password_data.password_type
        }
        
    except HTTPException:
        raise
    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"فشل تغيير كلمة المرور في MT5: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"حدث خطأ غير متوقع: {str(e)}"
        )
    finally:
        if conn:
            conn.close()
                        
####################################################################################################################################################
####################################################################################################################################################
####################################################################################################################################################
 
            
            


@router.post("/accounts/{login}/deposit", summary="إيداع أموال في حساب MT5")
async def deposit_to_mt5(login: int, transaction: MT5DepositWithdraw, user_data: dict = Depends(auth_scheme)):
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
            "message": "تم الإيداع بنجاح",
            "transaction_details": result
        }
    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"فشل عملية الإيداع: {e.message}"
        )

@router.post("/accounts/{login}/withdraw", summary="سحب أموال من حساب MT5")
async def withdraw_from_mt5(login: int, transaction: MT5DepositWithdraw, user_data: dict = Depends(auth_scheme)):
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
            "message": "تم السحب بنجاح",
            "transaction_details": result
        }
    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"فشل عملية السحب: {e.message}"
        )

@router.post("/accounts/transfer", summary="تحويل أموال بين حسابات MT5")
async def transfer_between_mt5(transfer: MT5Transfer, user_data: dict = Depends(auth_scheme)):
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
            "message": "تم التحويل بنجاح",
            "transaction_details": result
        }
    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"فشل عملية التحويل: {e.message}"
        )


@router.post("/accounts/{login}/enable-trading", summary="تمكين التداول لحساب MT5")
async def enable_mt5_trading(login: int, user_data: dict = Depends(auth_scheme)):
    """
    تمكين التداول لحساب MT5
    """
    client = get_mt5_client()
    try:
        result = client.enable_trading(login)
        return {
            "success": True,
            "message": "تم تمكين التداول بنجاح",
            "account_info": result
        }
    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"فشل تمكين التداول: {e.message}"
        )

@router.post("/accounts/{login}/disable-trading", summary="تعطيل التداول لحساب MT5")
async def disable_mt5_trading(login: int, user_data: dict = Depends(auth_scheme)):
    """
    تعطيل التداول لحساب MT5
    """
    client = get_mt5_client()
    try:
        result = client.disable_trading(login)
        return {
            "success": True,
            "message": "تم تعطيل التداول بنجاح",
            "account_info": result
        }
    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"فشل تعطيل التداول: {e.message}"
        )