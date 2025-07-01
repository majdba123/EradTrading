import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status, Query
from database.connection import get_db_connection
from schemas.users import ManagerCreate, ManagerFilter, UserStatusUpdate
from admin_auth import admin_scheme
from typing import Optional
from pydantic import BaseModel
from auth import TokenHandler
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from websocket_manager import websocket_manager
from auth import auth_scheme
import datetime
import json
import asyncio

router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


class UserNotificationCreate(BaseModel):
    user_id: int
    message: str


@router.post("/add-manager")
def add_manager(
    manager_data: ManagerCreate,
    admin_data: dict = Depends(admin_scheme)
):
    """Add a new manager with user account creation"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Begin transaction
        cursor.execute("BEGIN TRANSACTION")

        # 1. Create user account (manager)
        cursor.execute(
            """INSERT INTO users (phone, passcode, type, status)
               VALUES (?, ?, 2, 'active')""",
            (manager_data.phone, manager_data.passcode)
        )
        user_id = cursor.lastrowid

        # 2. Create manager record
        cursor.execute(
            """INSERT INTO managers (user_id, name)
               VALUES (?, ?)""",
            (user_id, manager_data.name)
        )

        # Commit transaction
        conn.commit()

        return {
            "success": True,
            "message": "Manager added successfully",
            "user_id": user_id,
            "phone": manager_data.phone,
            "name": manager_data.name
        }

    except sqlite3.IntegrityError as e:
        conn.rollback()
        if "UNIQUE constraint failed: users.phone" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add manager: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.get("/managers")
def get_all_managers(
    admin_data: dict = Depends(admin_scheme),
    page: int = Query(1, gt=0, description="Page number"),
    per_page: int = Query(10, gt=0, le=100, description="Items per page"),
    name: Optional[str] = Query(None, description="Filter by name"),
    phone: Optional[str] = Query(None, description="Filter by phone"),
    status: Optional[str] = Query(None, description="Filter by status")
):
    """Get list of all managers with pagination, filtering and sorting"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build SQL query with filters
        base_query = """
            SELECT 
                u.id as user_id,
                u.phone,
                u.status,
                m.name,
                m.created_at as manager_since
            FROM users u
            JOIN managers m ON u.id = m.user_id
            WHERE u.type = 1
        """

        filters = []
        params = []

        # Add filters if provided
        if name:
            filters.append("m.name LIKE ?")
            params.append(f"%{name}%")
        if phone:
            filters.append("u.phone LIKE ?")
            params.append(f"%{phone}%")
        if status:
            filters.append("u.status = ?")
            params.append(status)

        if filters:
            base_query += " AND " + " AND ".join(filters)

        # Add sorting by newest
        base_query += " ORDER BY m.created_at DESC"

        # Calculate pagination offset
        offset = (page - 1) * per_page

        # Total count query
        count_query = "SELECT COUNT(*) FROM (" + base_query + ")"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # Data query with pagination
        paginated_query = base_query + " LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        cursor.execute(paginated_query, params)

        # Transform results
        managers = []
        for row in cursor.fetchall():
            managers.append({
                "user_id": row[0],
                "phone": row[1],
                "status": row[2],
                "name": row[3],
                "manager_since": row[4]
            })

        return {
            "total_count": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": (total_count + per_page - 1) // per_page,
            "managers": managers
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch managers: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/managers/filter")
def filter_managers(
    filter_data: ManagerFilter,
    admin_data: dict = Depends(admin_scheme)
):
    """Get list of managers with filtering using JSON in Body"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build SQL query with filters
        base_query = """
            SELECT 
                u.id as user_id,
                u.phone,
                u.status,
                m.name,
                m.created_at as manager_since
            FROM users u
            JOIN managers m ON u.id = m.user_id
            WHERE u.type = 1
        """

        filters = []
        params = []

        # Add filters if provided
        if filter_data.name:
            filters.append("m.name LIKE ?")
            params.append(f"%{filter_data.name}%")
        if filter_data.phone:
            filters.append("u.phone LIKE ?")
            params.append(f"%{filter_data.phone}%")
        if filter_data.status:
            filters.append("u.status = ?")
            params.append(filter_data.status)

        if filters:
            base_query += " AND " + " AND ".join(filters)

        # Add sorting by newest
        base_query += " ORDER BY m.created_at DESC"

        # Calculate pagination offset
        offset = (filter_data.page - 1) * filter_data.per_page

        # Total count query
        count_query = "SELECT COUNT(*) FROM (" + base_query + ")"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # Data query with pagination
        paginated_query = base_query + " LIMIT ? OFFSET ?"
        params.extend([filter_data.per_page, offset])
        cursor.execute(paginated_query, params)

        # Transform results
        managers = []
        for row in cursor.fetchall():
            managers.append({
                "user_id": row[0],
                "phone": row[1],
                "status": row[2],
                "name": row[3],
                "manager_since": row[4]
            })

        return {
            "total_count": total_count,
            "page": filter_data.page,
            "per_page": filter_data.per_page,
            "total_pages": (total_count + filter_data.per_page - 1) // filter_data.per_page,
            "managers": managers
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch managers: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


class AssignUserRequest(BaseModel):
    user_id: int


@router.get("/managers-with-users")
def get_managers_with_users(
    admin_data: dict = Depends(admin_scheme)
):
    """Get all managers with their assigned users"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all managers
        cursor.execute("""
            SELECT m.id, m.name, u.phone, u.status
            FROM managers m
            JOIN users u ON m.user_id = u.id
            ORDER BY m.name
        """)
        managers = cursor.fetchall()

        result = []
        for manager in managers:
            # Get users assigned to each manager
            cursor.execute("""
                SELECT u.id, u.phone, u.status
                FROM manager_assignments ma
                JOIN users u ON ma.user_id = u.id
                WHERE ma.manager_id = ?
            """, (manager[0],))
            assigned_users = cursor.fetchall()

            result.append({
                "manager_id": manager[0],
                "manager_name": manager[1],
                "manager_phone": manager[2],
                "manager_status": manager[3],
                "assigned_users": [
                    {
                        "user_id": user[0],
                        "phone": user[1],
                        "status": user[2]
                    }
                    for user in assigned_users
                ]
            })

        return {"managers": result}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch data: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/assign-user-to-manager/{manager_id}")
def assign_user_to_manager(
    manager_id: int,
    request: AssignUserRequest,
    admin_data: dict = Depends(admin_scheme)
):
    """Assign user to manager with check for existing assignments"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify manager exists
        cursor.execute("SELECT id FROM managers WHERE id = ?", (manager_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Manager not found"
            )

        # Verify user exists
        cursor.execute("SELECT id, type FROM users WHERE id = ?",
                       (request.user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Verify user is not a manager
        if user[1] == 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign a manager to another manager"
            )

        # Check if user is already assigned to another manager
        cursor.execute("""
            SELECT manager_id FROM manager_assignments 
            WHERE user_id = ?
        """, (request.user_id,))
        existing_assignment = cursor.fetchone()

        if existing_assignment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User is already assigned to another manager (ID: {existing_assignment[0]})"
            )

        # Assign user to manager
        cursor.execute("""
            INSERT INTO manager_assignments (manager_id, user_id)
            VALUES (?, ?)
        """, (manager_id, request.user_id))

        conn.commit()
        return {
            "success": True,
            "message": "User assigned to manager successfully",
            "manager_id": manager_id,
            "user_id": request.user_id
        }

    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign user: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.delete("/delete-manager/{manager_id}")
def delete_manager(
    manager_id: int,
    admin_data: dict = Depends(admin_scheme)
):
    """Delete manager with check for assigned users"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Begin transaction
        cursor.execute("BEGIN TRANSACTION")

        # 1. Verify manager exists and count assigned users
        cursor.execute("""
            SELECT m.id, m.user_id, COUNT(ma.id) as assigned_users_count
            FROM managers m
            LEFT JOIN manager_assignments ma ON m.id = ma.manager_id
            WHERE m.id = ?
            GROUP BY m.id
        """, (manager_id,))

        manager_info = cursor.fetchone()

        if not manager_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Manager not found"
            )

        user_id = manager_info[1]
        assigned_users_count = manager_info[2]

        # 2. Prevent deletion if manager has assigned users
        if assigned_users_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete manager with {assigned_users_count} assigned users. Please unassign them first"
            )

        # 3. Delete manager record
        cursor.execute("""
            DELETE FROM managers 
            WHERE id = ?
        """, (manager_id,))

        # 4. Update user type to non-manager
        cursor.execute("""
            UPDATE users 
            SET type = 0 
            WHERE id = ? AND type = 1
        """, (user_id,))

        conn.commit()

        return {
            "success": True,
            "message": "Manager deleted successfully",
            "deleted_manager_id": manager_id,
            "user_downgraded": user_id
        }

    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete manager: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


class UnassignUserRequest(BaseModel):
    manager_id: int
    user_id: int


@router.post("/unassign-user")
def unassign_user(
    request: UnassignUserRequest,
    admin_data: dict = Depends(admin_scheme)
):
    """Unassign user from manager"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify assignment exists
        cursor.execute("""
            SELECT 1 FROM manager_assignments
            WHERE manager_id = ? AND user_id = ?
        """, (request.manager_id, request.user_id))

        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No assignment exists between manager and user"
            )

        # Remove assignment
        cursor.execute("""
            DELETE FROM manager_assignments
            WHERE manager_id = ? AND user_id = ?
        """, (request.manager_id, request.user_id))

        conn.commit()

        return {
            "success": True,
            "message": "User unassigned from manager successfully",
            "manager_id": request.manager_id,
            "user_id": request.user_id
        }

    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unassign user: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.get("/manager-users/{manager_id}")
def get_manager_users(
    manager_id: int,
    admin_data: dict = Depends(admin_scheme)
):
    """Get all users assigned to a specific manager"""
    conn = None
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row  # Important for dictionary conversion
        cursor = conn.cursor()

        # Verify manager exists
        cursor.execute("SELECT id FROM managers WHERE id = ?", (manager_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Manager not found"
            )

        # Get assigned users
        cursor.execute("""
            SELECT u.id, u.phone, u.status
            FROM manager_assignments ma
            JOIN users u ON ma.user_id = u.id
            WHERE ma.manager_id = ?
        """, (manager_id,))

        # Convert results to dictionaries
        users = []
        for row in cursor.fetchall():
            users.append({
                "user_id": row["id"],
                "phone": row["phone"],
                "status": row["status"]
            })

        return {
            "manager_id": manager_id,
            "assigned_users": users,
            "count": len(users)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch data: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


ALLOWED_STATUSES = ['pending', 'approved', 'rejected', 'banned']


@router.put("/update-user-status")
def update_user_status(
    status_data: UserStatusUpdate,
    admin_data: dict = Depends(admin_scheme)
):
    """Update user status with application ban check"""
    conn = None
    try:
        # Verify new status is allowed
        if status_data.new_status not in ALLOWED_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Allowed statuses: {', '.join(ALLOWED_STATUSES)}"
            )

        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Verify user exists and is not a manager
        cursor.execute(
            "SELECT id, type FROM users WHERE id = ?",
            (status_data.user_id,)
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if user[1] == 1:  # If user is a manager
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot change status of managers"
            )

        # 2. Update user status
        cursor.execute(
            "UPDATE users SET status = ? WHERE id = ?",
            (status_data.new_status, status_data.user_id)
        )

        # If user is banned, terminate all sessions
        if status_data.new_status == 'banned':
            cursor.execute(
                "DELETE FROM user_sessions WHERE user_id = ?",
                (status_data.user_id,)
            )

        conn.commit()

        return {
            "success": True,
            "message": f"User status updated to '{status_data.new_status}' successfully",
            "user_id": status_data.user_id,
            "new_status": status_data.new_status
        }

    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user status: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.get("/pending-accounts", summary="Get pending accounts for approval")
def get_pending_accounts(
    admin_data: dict = Depends(admin_scheme),
    page: int = Query(1, gt=0),
    per_page: int = Query(10, gt=0, le=100)
):
    """Get list of accounts waiting for admin approval"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Calculate pagination offset
        offset = (page - 1) * per_page

        # Total count query
        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE status = 'pending_approval'"
        )
        total_count = cursor.fetchone()[0]

        # Get paginated results
        cursor.execute(
            """SELECT id, phone, first_name, last_name, created_at 
            FROM users 
            WHERE status = 'pending_approval'
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?""",
            (per_page, offset)
        )

        accounts = []
        for row in cursor.fetchall():
            accounts.append({
                "user_id": row[0],
                "phone": row[1],
                "first_name": row[2],
                "last_name": row[3],
                "created_at": row[4]
            })

        return {
            "total_count": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": (total_count + per_page - 1) // per_page,
            "pending_accounts": accounts
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending accounts: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/approve-account/{user_id}", summary="Approve user account")
def approve_user_account(
    user_id: int,
    admin_data: dict = Depends(admin_scheme)
):
    """Approve a pending user account"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if user exists and is pending approval
        cursor.execute(
            "SELECT status FROM users WHERE id = ?",
            (user_id,)
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if user[0] != 'pending_approval':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account is not pending approval"
            )

        # Update user status to approved
        cursor.execute(
            "UPDATE users SET status = 'approved' WHERE id = ?",
            (user_id,)
        )
        conn.commit()

        return {
            "success": True,
            "message": "Account approved successfully",
            "user_id": user_id,
            "new_status": "approved"
        }

    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve account: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.post("/reject-account/{user_id}", summary="Reject user account")
async def reject_user_account(
    user_id: int,
    admin_data: dict = Depends(admin_scheme)
):
    """Reject a pending user account"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if user exists and is pending approval
        cursor.execute(
            "SELECT status FROM users WHERE id = ?",
            (user_id,)
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if user[0] != 'pending_approval':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account is not pending approval"
            )

        # Update user status to rejected
        cursor.execute(
            "UPDATE users SET status = 'rejected' WHERE id = ?",
            (user_id,)
        )

        # Delete any sessions or OTPs
        cursor.execute(
            "DELETE FROM user_sessions WHERE user_id = ?",
            (user_id,)
        )

        conn.commit()

        # Prepare notification
        notification = {
            "type": "account_rejected",
            "message": "Your account registration has been rejected by the administrator.",
            "timestamp": datetime.datetime.now().isoformat(),
            "user_id": user_id
        }

        # Send real-time notification
        await websocket_manager.send_personal_notification(str(user_id), notification)

        return {
            "success": True,
            "message": "Account rejected successfully",
            "user_id": user_id,
            "new_status": "rejected"
        }

    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject account: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.get("/sessions", summary="View all active sessions")
async def get_all_active_sessions(
    admin: dict = Depends(admin_scheme),
    page: int = Query(1, gt=0, description="Page number"),
    per_page: int = Query(10, gt=0, le=100, description="Items per page")
):
    """Admin only - View all active sessions with user information"""
    conn = None
    try:
        # Calculate pagination offset
        offset = (page - 1) * per_page

        conn = get_db_connection()
        cursor = conn.cursor()

        # Total count query
        cursor.execute("""
            SELECT COUNT(*) FROM user_sessions us
            JOIN users u ON us.user_id = u.id
            WHERE u.status != 'banned'
        """)
        total_count = cursor.fetchone()[0]

        # Get sessions from database with user info
        cursor.execute("""
            SELECT 
                us.id as session_id,
                us.token,
                us.created_at,
                u.id as user_id,
                u.phone,
                u.first_name,
                u.last_name,
                u.type as user_type,
                ud.ip_address,
                ud.device_name,
                ud.os,
                ud.browser,
                ud.country,
                ud.city
            FROM user_sessions us
            JOIN users u ON us.user_id = u.id
            LEFT JOIN user_devices ud ON (
                ud.user_id = u.id AND 
                ud.login_time = (
                    SELECT MAX(login_time) 
                    FROM user_devices 
                    WHERE user_id = u.id
                )
            )
            WHERE u.status != 'banned'
            ORDER BY us.created_at DESC
            LIMIT ? OFFSET ?
        """, (per_page, offset))

        db_sessions = []
        for row in cursor.fetchall():
            db_sessions.append({
                "session_id": row[0],
                "token": row[1],
                "login_time": row[2],
                "user_id": row[3],
                "phone": row[4],
                "user_name": f"{row[5] or ''} {row[6] or ''}".strip(),
                "user_type": "Manager" if row[7] == 1 else "Regular user",
                "device_info": {
                    "ip_address": row[8],
                    "device_name": row[9],
                    "os": row[10],
                    "browser": row[11],
                    "country": row[12],
                    "city": row[13]
                },
                "source": "database"
            })

        # Get sessions from memory cache via TokenHandler
        memory_sessions = []
        # Use the get_all_sessions method from TokenHandler
        raw_memory_sessions = TokenHandler.get_all_sessions()

        for session in raw_memory_sessions:
            memory_sessions.append({
                "token": session["token"],
                "login_time": session["login_time"],
                "user_id": session["user_id"],
                "user_type": "Manager" if session["user_type"] == 1 else "Regular user",
                "device_info": session.get("device_info", {}),
                "source": "memory_cache"
            })

        all_sessions = db_sessions + [
            s for s in memory_sessions
            if not any(ds['token'] == s['token'] for ds in db_sessions)
        ]

        return {
            "total_count": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": (total_count + per_page - 1) // per_page,
            "sessions": all_sessions,
            "stats": {
                "database_sessions": len(db_sessions),
                "memory_cache_sessions": len(memory_sessions),
                "active_sessions": len(all_sessions)
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch sessions: {str(e)}"
        )
    finally:
        if conn:
            conn.close()
