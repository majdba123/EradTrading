# routers/admin_account_types.py
from fastapi import APIRouter, Depends, HTTPException
from database.connection import get_db_connection
from auth import auth_scheme
from pydantic import BaseModel
from typing import List
import sqlite3

router = APIRouter(tags=["Account Types Management"])


class AccountTypeCreate(BaseModel):
    name: str


class AccountTypeUpdate(BaseModel):
    name: str = None


@router.post("/account-types", status_code=201)
async def create_account_type(
    account_type: AccountTypeCreate,
    admin_data: dict = Depends(auth_scheme)
):
    """Create a new account type (Admin only)"""
    if admin_data["user_type"] != 1:
        raise HTTPException(
            status_code=403, detail="Only admins can create account types")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert new account type into database
        cursor.execute(
            """INSERT INTO account_types 
            (name)
            VALUES (?)""",
            (account_type.name,)
        )
        conn.commit()

        return {
            "success": True,
            "message": "Account type created successfully",
            "account_type_id": cursor.lastrowid
        }
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400,
            detail="Account type with this name already exists"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create account type: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.get("/account-types", response_model=List[dict])
async def get_all_account_types(
    admin_data: dict = Depends(auth_scheme)
):
    """Get all account types (Admin only)"""
    if admin_data["user_type"] != 1:
        raise HTTPException(
            status_code=403, detail="Only admins can view account types")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch all account types ordered by name
        cursor.execute(
            """SELECT id, name
            FROM account_types
            ORDER BY name"""
        )

        return [
            {
                "id": row[0],
                "name": row[1],
            }
            for row in cursor.fetchall()
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch account types: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.put("/account-types/{type_id}")
async def update_account_type(
    type_id: int,
    account_type: AccountTypeUpdate,
    admin_data: dict = Depends(auth_scheme)
):
    """Update an account type (Admin only)"""
    if admin_data["user_type"] != 1:
        raise HTTPException(
            status_code=403, detail="Only admins can update account types")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Prepare dynamic update fields
        update_fields = []
        params = []

        if account_type.name is not None:
            update_fields.append("name = ?")
            params.append(account_type.name)

        if not update_fields:
            raise HTTPException(
                status_code=400,
                detail="No fields provided for update"
            )

        params.append(type_id)

        # Build dynamic update query
        query = f"""
        UPDATE account_types 
        SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """

        cursor.execute(query, params)
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404, detail="Account type not found")

        return {
            "success": True,
            "message": "Account type updated successfully"
        }
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400,
            detail="Account type with this name already exists"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update account type: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.delete("/account-types/{type_id}")
async def delete_account_type(
    type_id: int,
    admin_data: dict = Depends(auth_scheme)
):
    """Delete an account type (Admin only)"""
    if admin_data["user_type"] != 1:
        raise HTTPException(
            status_code=403, detail="Only admins can delete account types")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if any accounts are using this type
        cursor.execute(
            "SELECT 1 FROM user_mt5_accounts WHERE account_type = ? LIMIT 1",
            (type_id,)
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="Cannot delete account type with associated accounts"
            )

        # Delete the account type
        cursor.execute(
            "DELETE FROM account_types WHERE id = ?",
            (type_id,)
        )
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404, detail="Account type not found")

        return {
            "success": True,
            "message": "Account type deleted successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete account type: {str(e)}"
        )
    finally:
        if conn:
            conn.close()
