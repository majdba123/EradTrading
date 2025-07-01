import sqlite3
from security import cipher  # Import encryption object
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


@router.post("/accounts", response_model=dict, summary="Create New Account Request")
async def create_mt5_account_request(
    account_data: dict,
    request: Request,
    user_data: dict = Depends(auth_scheme),
    _: bool = Depends(check_permission),
):
    """
    Create new MT5 account request (requires admin approval)
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify account type exists in account_types table
        cursor.execute(
            "SELECT id FROM account_types WHERE name = ?",
            (account_data["account_type"],)
        )
        account_type = cursor.fetchone()

        if not account_type:
            raise HTTPException(
                status_code=400,
                detail="Invalid account type. Please select an existing account type."
            )

        # Get user data for verification
        cursor.execute(
            "SELECT id FROM users WHERE id = ?",
            (user_data["user_id"],)
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Store account request in database (without MT5 data yet)
        cursor.execute(
            """INSERT INTO user_mt5_accounts 
            (user_id, account_type, status) 
            VALUES (?, ?, ?)""",
            (
                user_data["user_id"],
                account_data["account_type"],
                "pending"  # Default status
            )
        )
        conn.commit()

        return {
            "success": True,
            "message": "MT5 account request created successfully and is pending admin approval",
            "status": "pending"
        }

    except sqlite3.IntegrityError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Account request creation error: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/accounts/approve/{account_id}", response_model=dict, summary="Approve MT5 Account")
async def approve_mt5_account(
    account_id: int,
    request: Request,
    user_data: dict = Depends(auth_scheme),
    _: bool = Depends(check_permission),
):
    """
    Approve MT5 account and create it in the MT5 system
    """
    client = get_mt5_client()
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get request data
        cursor.execute(
            """SELECT u.id, u.first_name, u.last_name, a.account_type 
            FROM user_mt5_accounts a
            JOIN users u ON a.user_id = u.id
            WHERE a.id = ? AND a.status = 'pending'""",
            (account_id,)
        )
        account_request = cursor.fetchone()

        if not account_request:
            raise HTTPException(
                status_code=404,
                detail="Account request not found or not in pending status"
            )

        user_id, first_name, last_name, account_type = account_request

        # Create account in MT5
        result = client.create_account(
            first_name=first_name,
            last_name=last_name,
            account_type=account_type
        )
        encrypted_password = cipher.encrypt_password(result["password"])
        encrypted_investor_password = cipher.encrypt_password(
            result["investor_password"])

        # Update account record with actual MT5 data
        cursor.execute(
            """UPDATE user_mt5_accounts 
            SET mt5_login_id = ?, 
                mt5_password = ?, 
                mt5_investor_password = ?,
                status = 'approved'
            WHERE id = ?""",
            (
                result["login"],
                encrypted_password,
                encrypted_investor_password,
                account_id
            )
        )
        conn.commit()

        return {
            "success": True,
            "message": "Account approved and created in MT5 system successfully",
            "account_id": account_id,
            "mt5_login_id": result["login"],
            "new_status": "approved"
        }

    except HTTPException:
        raise
    except Exception as e:
        # If MT5 account creation fails, revert status to pending
        if conn:
            cursor.execute(
                "UPDATE user_mt5_accounts SET status = 'pending' WHERE id = ?",
                (account_id,)
            )
            conn.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating account in MT5: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/accounts/reject/{account_id}", response_model=dict, summary="Reject MT5 Account")
async def reject_mt5_account(
    account_id: int,
    request: Request,
    user_data: dict = Depends(auth_scheme),
    _: bool = Depends(check_permission),
):
    """
    Reject MT5 account creation request
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify request exists
        cursor.execute(
            "SELECT id FROM user_mt5_accounts WHERE id = ? AND status = 'pending'",
            (account_id,)
        )
        account = cursor.fetchone()

        if not account:
            raise HTTPException(
                status_code=404,
                detail="Account request not found or not in pending status"
            )

        # Update account status to rejected
        cursor.execute(
            "UPDATE user_mt5_accounts SET status = 'rejected' WHERE id = ?",
            (account_id,)
        )
        conn.commit()

        return {
            "success": True,
            "message": "Account request rejected successfully",
            "account_id": account_id,
            "new_status": "rejected"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.get("/accounts/my-accounts", response_model=list, summary="Get all my MT5 accounts")
async def get_my_mt5_accounts(user_data: dict = Depends(auth_scheme),
                              _: bool = Depends(check_permission),
                              has_permission: bool = Depends(
                                  UserPermissionChecker("mt5_get_accounts"))
                              ):
    """
    Get all MT5 accounts for current user with decrypted passwords

    For each request:
    1. Get accounts from database
    2. Decrypt passwords for each account
    3. Return data with decrypted passwords
    """
    conn = None
    try:
        # 1. Get accounts from database
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

            # 2. Decrypt passwords for each account
            try:
                # Get decrypted main password
                password = cipher.decrypt_password(
                    account[1]) if account[1] else None

                # Get decrypted investor password
                investor_password = cipher.decrypt_password(
                    account[2]) if account[2] else None

                # 3. Add account with decrypted passwords
                result.append({
                    "login": login,
                    "password": password,
                    "investor_password": investor_password,
                    "type": account[3],
                    "created_at": account[4]
                })

            except Exception as decrypt_error:
                # If decryption fails, return hidden password
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


@router.get("/accounts/{login}", response_model=MT5AccountInfo, summary="Get MT5 account information")
async def get_mt5_account(login: int, user_data: dict = Depends(auth_scheme), _: bool = Depends(check_permission),
                          has_permission: bool = Depends(UserPermissionChecker("mt5_get_accounts"))):
    """
    Get MT5 account information

    Requirements:
    - **login**: MT5 account number (must belong to authenticated user)
    """
    conn = None
    try:
        # Verify account belongs to authenticated user
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

        # Get account info from MT5
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


@router.post("/auth/send-otp", response_model=dict, summary="Send OTP verification code")
async def send_otp(
    phone_data: dict,
    user_data: dict = Depends(auth_scheme), _: bool = Depends(check_permission),
    has_permission: bool = Depends(UserPermissionChecker("mt5_get_accounts"))
):
    """
    Send OTP code to phone number

    Required:
    {
        "phone": "Phone number (with country code)"
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
            # Reference for later verification
            "otp_ref": result.get("otp_ref"),
            "expires_in": 300  # Seconds (5 minutes)
        }

    except SCBAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to send code: {e}"
        )


@router.post("/accounts/change-password/{login}/", summary="Change MT5 account password")
async def change_mt5_password(
    login: int,
    password_data: MT5PasswordChange,
    user_data: dict = Depends(auth_scheme),
    _: bool = Depends(check_permission),
    has_permission: bool = Depends(UserPermissionChecker("mt5_get_accounts"))
):
    """
    Change MT5 account password and update in database

    Requirements:
    - **new_password**: New password
    - **password_type**: Password type (MAIN or INVESTOR)
    """
    conn = None
    try:
        # Verify account belongs to current user
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

        # Change password in MT5
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

        # Update password in database (with encryption)
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


@router.post("/accounts/check-password/{login_id}", response_model=dict, summary="Verify your MT5 account password")
async def verify_mt5_password(
    login_id: int,  # Receives login_id as path parameter
    password_request: dict,  # Receives password and type
    user_data: dict = Depends(auth_scheme), _: bool = Depends(check_permission),
    has_permission: bool = Depends(UserPermissionChecker("mt5_get_accounts"))
):
    """
    Verify MT5 account password with account ownership verification

    Required:
    - Path Parameter: login_id (MT5 account number)
    - Request Body:
    {
        "password": "Password to verify",
        "password_type": "MAIN" or "INVESTOR" (optional - default MAIN)
    }

    Process:
    1. Verify login_id belongs to authenticated user
    2. Verify password with MT5
    3. Return verification result
    """
    conn = None
    try:
        # 1. Verify required data exists
        if not password_request.get("password"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be entered"
            )

        password = password_request["password"]
        password_type = password_request.get("password_type", "MAIN")

        # 2. Verify account belongs to user
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

        # 3. Verify password with MT5
        client = get_mt5_client()
        is_valid = client.check_password(
            login=login_id,
            password=password,
            password_type=password_type
        )

        # 4. Return result
        return {
            "success": True,
            "login_id": login_id,
            "password_type": password_type,
            "is_valid": is_valid,
            "message": "The password is correct" if is_valid else "The password is incorrect.",
            "user_verified": True  # Confirm user owns this account
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


@router.post("/accounts/update-rights/{login_id}",
             response_model=dict,
             summary="Update MT5 account permissions")
async def update_mt5_user_rights(
    login_id: int,
    rights_data: dict,
    user_data: dict = Depends(auth_scheme), _: bool = Depends(check_permission),
    has_permission: bool = Depends(UserPermissionChecker("mt5_get_accounts"))
):
    """
    Update MT5 account permissions and settings with account ownership verification

    Required:
    - Path Parameter: login_id (MT5 account number)
    - Request Body:
    {
        "rights": {
            "USER_RIGHT_ENABLED": 1,       // 1 to enable, 0 to disable
            "USER_RIGHT_TRADE_DISABLED": 0  // 1 to disable trading, 0 to enable
        },
        "params": {                        // optional
            "leverage": 100,               // leverage
            "email": "user@example.com"    // email
        }
    }
    """
    conn = None
    try:
        # 1. Verify account ownership
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

        # 2. Verify required data exists
        if not rights_data.get("rights"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The required authorization data must be provided."
            )

        rights = rights_data["rights"]
        params = rights_data.get("params", {})

        # 3. Update permissions in MT5
        client = get_mt5_client()
        result = client.update_user_rights(
            login=login_id,
            rights=rights,
            params=params
        )

        # 4. Return result
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


@router.post("/accounts/{login}/deposit", summary="Deposit funds into an MT5 account")
async def deposit_to_mt5(login: int, transaction: MT5DepositWithdraw, user_data: dict = Depends(auth_scheme), _: bool = Depends(check_permission),
                         has_permission: bool = Depends(UserPermissionChecker("mt5_get_accounts"))):
    """
    Deposit funds into MT5 account

    Requirements:
    - **amount**: Amount to deposit
    - **comment**: Transaction comment (optional)
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
                            has_permission: bool = Depends(UserPermissionChecker("mt5_get_accounts"))):
    """
    Withdraw funds from MT5 account

    Requirements:
    - **amount**: Amount to withdraw
    - **comment**: Transaction comment (optional)
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
                               has_permission: bool = Depends(UserPermissionChecker("mt5_get_accounts"))):
    """
    Transfer funds between MT5 accounts

    Requirements:
    - **from_login**: Source account
    - **to_login**: Destination account
    - **amount**: Amount to transfer
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
                             has_permission: bool = Depends(UserPermissionChecker("mt5_get_accounts"))):
    """
    Enable trading for MT5 account
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
                              has_permission: bool = Depends(UserPermissionChecker("mt5_get_accounts"))):
    """
    Disable trading for MT5 account
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
