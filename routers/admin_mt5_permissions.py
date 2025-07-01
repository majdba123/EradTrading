# routers/admin_mt5_permissions.py
from fastapi import APIRouter, Depends, HTTPException
from database.connection import get_db_connection
from auth import auth_scheme
import sqlite3

router = APIRouter(tags=["MT5 Permissions Management"])


def initialize_mt5_permissions():
    """Initialize MT5 API permissions in the database"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # List of all MT5 API endpoints with their descriptions
        mt5_endpoints = [
            {
                "name": "mt5_create_account",
                "path": "/api/mt5/accounts",
                "description": "Create new MT5 account",
                "required_permission": "mt5_account_management"
            },
            {
                "name": "mt5_get_accounts",
                "path": "/api/mt5/accounts/my-accounts",
                "description": "Get all user's MT5 accounts",
                "required_permission": "mt5_account_view"
            },
            {
                "name": "mt5_get_account_info",
                "path": "/api/mt5/accounts/{login}",
                "description": "Get MT5 account information",
                "required_permission": "mt5_account_view"
            },
            {
                "name": "mt5_send_otp",
                "path": "/api/mt5/auth/send-otp",
                "description": "Send OTP verification code",
                "required_permission": "mt5_auth"
            },
            {
                "name": "mt5_change_password",
                "path": "/api/mt5/accounts/change-password/{login}/",
                "description": "Change MT5 account password",
                "required_permission": "mt5_account_management"
            },
            {
                "name": "mt5_check_password",
                "path": "/api/mt5/accounts/check-password/{login_id}",
                "description": "Verify MT5 account password",
                "required_permission": "mt5_auth"
            },
            {
                "name": "mt5_update_rights",
                "path": "/api/mt5/accounts/update-rights/{login_id}",
                "description": "Update MT5 account permissions",
                "required_permission": "mt5_account_management"
            },
            {
                "name": "mt5_deposit",
                "path": "/api/mt5/accounts/{login}/deposit",
                "description": "Deposit funds to MT5 account",
                "required_permission": "mt5_financial_operations"
            },
            {
                "name": "mt5_withdraw",
                "path": "/api/mt5/accounts/{login}/withdraw",
                "description": "Withdraw funds from MT5 account",
                "required_permission": "mt5_financial_operations"
            },
            {
                "name": "mt5_transfer",
                "path": "/api/mt5/accounts/transfer",
                "description": "Transfer funds between MT5 accounts",
                "required_permission": "mt5_financial_operations"
            },
            {
                "name": "mt5_enable_trading",
                "path": "/api/mt5/accounts/{login}/enable-trading",
                "description": "Enable trading for MT5 account",
                "required_permission": "mt5_trading_management"
            },
            {
                "name": "mt5_disable_trading",
                "path": "/api/mt5/accounts/{login}/disable-trading",
                "description": "Disable trading for MT5 account",
                "required_permission": "mt5_trading_management"
            }
        ]

        for endpoint in mt5_endpoints:
            # Check if permission already exists
            cursor.execute(
                "SELECT 1 FROM permissions WHERE endpoint_name = ?",
                (endpoint["name"],)
            )
            if not cursor.fetchone():
                cursor.execute(
                    """INSERT INTO permissions
                    (endpoint_name, endpoint_path, description,
                     required_permission, is_active)
                    VALUES (?, ?, ?, ?, 1)""",
                    (
                        endpoint["name"],
                        endpoint["path"],
                        endpoint["description"],
                        endpoint["required_permission"]
                    )
                )

        conn.commit()
    except Exception as e:
        print(f"Error initializing MT5 permissions: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()


@router.get("/mt5/permissions", summary="Get all MT5 API permissions")
async def get_mt5_permissions(user_data: dict = Depends(auth_scheme)):
    """
    Get list of all MT5 API permissions with their current status
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT id, endpoint_name, endpoint_path, is_active, description, required_permission 
               FROM permissions 
               WHERE endpoint_path LIKE '/api/mt5%'
               ORDER BY endpoint_name"""
        )

        permissions = cursor.fetchall()

        return {
            "success": True,
            "permissions": [
                {
                    "id": p[0],
                    "name": p[1],
                    "path": p[2],
                    "is_active": bool(p[3]),
                    "description": p[4],
                    "required_permission": p[5]
                }
                for p in permissions
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch permissions: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.put("/mt5/permissions/{permission_id}", summary="Update MT5 permission status")
async def update_mt5_permission(
    permission_id: int,
    update_data: dict,
    user_data: dict = Depends(auth_scheme)
):
    """
    Update MT5 permission status

    Required:
    {
        "is_active": true/false  // New permission status
    }
    """
    conn = None
    try:
        is_active = update_data.get("is_active", False)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify permission exists
        cursor.execute(
            "SELECT 1 FROM permissions WHERE id = ? AND endpoint_path LIKE '/api/mt5%'",
            (permission_id,)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail="Permission not found or not an MT5 permission"
            )

        # Update status
        cursor.execute(
            "UPDATE permissions SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (1 if is_active else 0, permission_id)
        )
        conn.commit()

        return {
            "success": True,
            "message": "Permission updated successfully",
            "permission_id": permission_id,
            "new_status": "active" if is_active else "inactive"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update permission: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/block-permission", status_code=200)
async def block_user_permission(
    block_data: dict,
    admin_data: dict = Depends(auth_scheme)
):
    """
    Block user from specific permission

    Required: {"user_id": int, "permission_id": int}
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO user_deny_permissions (user_id, permission_id)
            VALUES (?, ?)""",
            (block_data["user_id"], block_data["permission_id"])
        )
        conn.commit()

        return {
            "success": True,
            "message": "User blocked from permission successfully"
        }
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400,
            detail="User is already blocked from this permission"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error blocking permission: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/unblock-permission", status_code=200)
async def unblock_user_permission(
    unblock_data: dict,
    admin_data: dict = Depends(auth_scheme)
):
    """
    Unblock user from specific permission

    Required: {"user_id": int, "permission_id": int}
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """DELETE FROM user_deny_permissions
            WHERE user_id = ? AND permission_id = ?""",
            (unblock_data["user_id"], unblock_data["permission_id"])
        )
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="No such permission block found"
            )

        return {
            "success": True,
            "message": "User unblocked from permission successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error unblocking permission: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.get("/user-blocked-permissions/{user_id}")
async def get_user_blocked_permissions(
    user_id: int,
    admin_data: dict = Depends(auth_scheme)
):
    """Get list of all blocked permissions for a specific user"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT p.id, p.endpoint_name, p.endpoint_path, p.description
            FROM permissions p
            JOIN user_deny_permissions udp ON p.id = udp.permission_id
            WHERE udp.user_id = ?""",
            (user_id,)
        )

        permissions = cursor.fetchall()

        return {
            "success": True,
            "user_id": user_id,
            "blocked_permissions": [
                {
                    "permission_id": p[0],
                    "endpoint_name": p[1],
                    "endpoint_path": p[2],
                    "description": p[3]
                }
                for p in permissions
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching blocked permissions: {str(e)}"
        )
    finally:
        if conn:
            conn.close()
