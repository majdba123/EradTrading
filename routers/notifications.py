# routers/notifications.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi import APIRouter, Depends, HTTPException, status
from database.connection import get_db_connection
from auth import auth_scheme
from typing import List, Optional
from pydantic import BaseModel
import sqlite3
from datetime import datetime
from websocket_manager import websocket_manager  # Import WebSocket manager
import asyncio

from fastapi import Query, HTTPException
router = APIRouter(tags=["Notifications"])


class NotificationCreate(BaseModel):
    message: str
    user_id: int = None  # Optional for admin notifications


class NotificationUpdate(BaseModel):
    message: str


class Is_Read(BaseModel):
    is_read: int = 3  # Optional for admin notifications


# --- Admin Notifications (Application-wide) ---


@router.post("/admin/notifications", status_code=201)
async def create_admin_notification(
    notification: NotificationCreate,
    admin_data: dict = Depends(auth_scheme)
):
    """Create application-wide notification (for all users)"""
    if admin_data["user_type"] != 1:  # 1 for admin
        raise HTTPException(
            status_code=403, detail="Only admins can create global notifications")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # is_admin=1 for global notifications
        cursor.execute(
            """INSERT INTO notifications (user_id, message, is_admin)
            VALUES (?, ?, 1)""",
            (0, notification.message)  # user_id=0 for global notifications
        )
        conn.commit()

        broadcast_msg = {
            "type": "admin_notification",  # Add this field
            "message": notification.message,  # Ensure "message" field exists
            "timestamp": datetime.now().isoformat()
        }
        # Number of connections
        print(
            f"Broadcasting to {len(websocket_manager.active_public_connections)} public connections")
        await websocket_manager.broadcast_notification(broadcast_msg)

        return {
            "success": True,
            "message": "Admin notification created successfully",
            "notification_id": cursor.lastrowid
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create admin notification: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.get("/admin/notifications", response_model=List[dict])
async def get_all_admin_notifications(
    admin_data: dict = Depends(auth_scheme)
):
    """Get all admin notifications (application-wide)"""
    if admin_data["user_type"] != 1:
        raise HTTPException(
            status_code=403, detail="Only admins can view global notifications")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT id, message, created_at
            FROM notifications
            WHERE is_admin = 1
            ORDER BY created_at DESC"""
        )

        notifications = []
        for row in cursor.fetchall():
            notifications.append({
                "id": row[0],
                "message": row[1],
                "created_at": row[2]
            })

        return notifications
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch admin notifications: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.put("/admin/notifications/{notification_id}")
async def update_admin_notification(
    notification_id: int,
    notification: NotificationUpdate,
    admin_data: dict = Depends(auth_scheme)
):
    """Update admin notification"""
    if admin_data["user_type"] != 1:
        raise HTTPException(
            status_code=403, detail="Only admins can update global notifications")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """UPDATE notifications
            SET message = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND is_admin = 1""",
            (notification.message, notification_id)
        )
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404, detail="Admin notification not found")

        return {
            "success": True,
            "message": "Admin notification updated successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update admin notification: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.delete("/admin/notifications/{notification_id}")
async def delete_admin_notification(
    notification_id: int,
    admin_data: dict = Depends(auth_scheme)
):
    """Delete admin notification"""
    if admin_data["user_type"] != 1:
        raise HTTPException(
            status_code=403, detail="Only admins can delete global notifications")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM notifications WHERE id = ? AND is_admin = 1",
            (notification_id,)
        )
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404, detail="Admin notification not found")

        return {
            "success": True,
            "message": "Admin notification deleted successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete admin notification: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


class NotificationBase(BaseModel):
    message: str
    user_id: Optional[int] = None  # Required when is_admin=0


class NotificationBase2(BaseModel):
    message: str


@router.post("/admin/user-notifications", status_code=201)
async def create_user_notification(
    notification: NotificationBase,
    admin_data: dict = Depends(auth_scheme)
):
    """Create notification for specific user (is_admin=0)"""
    if admin_data.get("user_type") != 1:
        raise HTTPException(
            status_code=403, detail="Only admins can create user notifications")

    if not notification.user_id:
        raise HTTPException(status_code=400, detail="User ID is required")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify user exists
        cursor.execute("SELECT 1 FROM users WHERE id = ?",
                       (notification.user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        # Insert notification into database
        cursor.execute(
            """INSERT INTO notifications (user_id, message, is_admin)
            VALUES (?, ?, ?)""",
            (notification.user_id, notification.message, 0)
        )
        notification_id = cursor.lastrowid

        # Prepare WebSocket notification
        ws_notification = {
            "type": "status_update",
            "message": notification.message,
            "timestamp": datetime.now().isoformat(),
            "user_id": str(notification.user_id)
        }

        # Send real-time notification
        print(
            f"Attempting to send notification to user {notification.user_id}")
        await websocket_manager.send_personal_notification(str(notification.user_id), ws_notification)
        await asyncio.sleep(0.1)

        print("Notification sent successfully")

        # Store notification in database (if store_notification is required)
        try:
            from models.notifications import store_notification
            stored_id = store_notification(
                user_id=notification.user_id,
                message=notification.message,
                is_admin=False
            )
            print(f"Notification stored in database with ID: {stored_id}")
        except Exception as e:
            print(f"Failed to store notification: {str(e)}")

        conn.commit()

        return {
            "success": True,
            "message": "User notification created",
            "notification_id": notification_id
        }

    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create user notification: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.get("/admin/user-notifications/{user_id}", response_model=List[dict])
async def get_user_notifications(
    user_id: int,
    admin_data: dict = Depends(auth_scheme)
):
    """Get notifications for specific user (admin only)"""
    if admin_data["user_type"] != 1:
        raise HTTPException(
            status_code=403, detail="Only admins can view user notifications")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT id, message, is_read, created_at 
            FROM notifications 
            WHERE user_id = ? AND is_admin = 0
            ORDER BY created_at DESC""",
            (user_id,)
        )

        return [
            {
                "id": row[0],
                "message": row[1],
                "is_read": bool(row[2]),
                "created_at": row[3]
            }
            for row in cursor.fetchall()
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch user notifications: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.put("/admin/user-notifications/{notification_id}")
async def update_user_notification(
    notification_id: int,
    notification: NotificationBase2,  # Without user_id field now
    admin_data: dict = Depends(auth_scheme)
):
    """Update content of user notification (preserving original user_id)"""
    if admin_data["user_type"] != 1:
        raise HTTPException(
            status_code=403,
            detail="Only admins can update user notifications"
        )

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get original user_id first
        cursor.execute(
            "SELECT user_id FROM notifications WHERE id = ? AND is_admin = 0",
            (notification_id,)
        )
        existing_notification = cursor.fetchone()

        if not existing_notification:
            raise HTTPException(
                status_code=404,
                detail="User notification not found or not editable"
            )

        # Update while preserving original user_id
        cursor.execute(
            """UPDATE notifications 
            SET message = ?
            WHERE id = ? AND is_admin = 0""",
            (notification.message, notification_id)
        )
        conn.commit()

        return {
            "success": True,
            "message": "User notification content updated successfully",
            "user_id": existing_notification[0]  # Return original user_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update user notification: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.delete("/admin/user-notifications/{notification_id}")
async def delete_user_notification(
    notification_id: int,
    admin_data: dict = Depends(auth_scheme)
):
    """Delete user notification (admin only)"""
    if admin_data["user_type"] != 1:
        raise HTTPException(
            status_code=403,
            detail="Only admins can delete user notifications"
        )

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify notification exists and is user type (is_admin=0)
        cursor.execute(
            "DELETE FROM notifications WHERE id = ? AND is_admin = 0",
            (notification_id,)
        )
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="User notification not found or not deletable"
            )

        return {
            "success": True,
            "message": "User notification deleted successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete user notification: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.get("/user/my-notifications", response_model=List[dict])
async def get_my_notifications(
    is_read: Optional[int] = Query(
        3, description="Filter by read status (0=unread, 1=read, 3=all)"),
    user_data: dict = Depends(auth_scheme)
):
    """Get my notifications with flexible read status filtering"""
    print(
        f"DEBUG: Received request - is_read={is_read}, user_id={user_data.get('user_id')}")  # Debug log

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Debug: Verify database connection
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        print(f"DEBUG: Tables in database: {cursor.fetchall()}")

        # Base query
        query = """
            SELECT id, message, is_admin, is_read, created_at 
            FROM notifications 
            WHERE (user_id = ? OR (is_admin = 1 AND user_id IS NULL))
        """
        params = [user_data["user_id"]]

        # Add read status filter if specified (0 or 1)
        if is_read in [0, 1]:
            query += " AND is_read = ?"
            params.append(is_read)
        elif is_read != 3:
            raise HTTPException(
                status_code=400,
                detail="Invalid is_read value. Use 0 (unread), 1 (read), or 3 (all)"
            )

        query += " ORDER BY created_at DESC"

        print(f"DEBUG: Final query: {query}")  # Debug log
        print(f"DEBUG: Query params: {params}")  # Debug log

        # Execute query
        cursor.execute(query, tuple(params))
        results = cursor.fetchall()
        print(f"DEBUG: Raw results from DB: {results}")  # Debug log

        notifications = [{
            "id": row[0],
            "message": row[1],
            "is_admin": bool(row[2]),
            "is_read": bool(row[3]),
            "created_at": row[4],
            "type": "admin" if row[2] else "user"
        } for row in results]

        print(f"DEBUG: Processed notifications: {notifications}")  # Debug log
        return notifications

    except Exception as e:
        print(f"ERROR: {str(e)}")  # Debug log
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch notifications: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.put("/user/notifications/mark-all-read")
async def mark_all_as_read(
    user_data: dict = Depends(auth_scheme)
):
    """Mark all user notifications as read"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Update all unread user notifications
        cursor.execute(
            """UPDATE notifications 
            SET is_read = 1 
            WHERE (user_id = ? OR (is_admin = 1 AND user_id IS NULL))
            AND is_read = 0""",
            (user_data["user_id"],)
        )

        updated_count = cursor.rowcount
        conn.commit()

        return {
            "success": True,
            "message": f"Marked {updated_count} notifications as read",
            "updated_count": updated_count
        }

    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notifications: {str(e)}"
        )
    finally:
        if conn:
            conn.close()
