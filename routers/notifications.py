# routers/notifications.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi import APIRouter, Depends, HTTPException, status
from database.connection import get_db_connection
from auth import auth_scheme
from typing import List, Optional
from pydantic import BaseModel
import sqlite3

router = APIRouter(tags=["Notifications"])


class NotificationCreate(BaseModel):
    message: str
    user_id: int = None  # Optional for admin notifications


class NotificationUpdate(BaseModel):
    message: str

# --- إشعارات الأدمن (على مستوى التطبيق) ---


@router.post("/admin/notifications", status_code=201)
async def create_admin_notification(
    notification: NotificationCreate,
    admin_data: dict = Depends(auth_scheme)
):
    """إنشاء إشعار على مستوى التطبيق (لجميع المستخدمين)"""
    if admin_data["user_type"] != 1:  # 1 for admin
        raise HTTPException(
            status_code=403, detail="Only admins can create global notifications")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # is_admin=1 للإشعارات العامة
        cursor.execute(
            """INSERT INTO notifications (user_id, message, is_admin)
            VALUES (?, ?, 1)""",
            (0, notification.message)  # user_id=0 للإشعارات العامة
        )
        conn.commit()

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
    """الحصول على جميع إشعارات الأدمن (على مستوى التطبيق)"""
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
    """تحديث إشعار أدمن"""
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
    """حذف إشعار أدمن"""
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
    """إنشاء إشعار لمستخدم معين (is_admin=0)"""
    if admin_data["user_type"] != 1:
        raise HTTPException(
            status_code=403, detail="Only admins can create user notifications")

    if not notification.user_id:
        raise HTTPException(status_code=400, detail="User ID is required")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # التحقق من وجود المستخدم
        cursor.execute("SELECT 1 FROM users WHERE id = ?",
                       (notification.user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        cursor.execute(
            """INSERT INTO notifications (user_id, message, is_admin)
            VALUES (?, ?, ?)""",
            (notification.user_id, notification.message, 0)
        )
        conn.commit()

        return {
            "success": True,
            "message": "User notification created",
            "notification_id": cursor.lastrowid
        }
    except Exception as e:
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
    """الحصول على إشعارات مستخدم معين (للأدمن)"""
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
    notification: NotificationBase2,  # بدون حقل user_id الآن
    admin_data: dict = Depends(auth_scheme)
):
    """تعديل محتوى إشعار لمستخدم معين (مع الحفاظ على user_id الأصلي)"""
    if admin_data["user_type"] != 1:
        raise HTTPException(
            status_code=403,
            detail="Only admins can update user notifications"
        )

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # جلب user_id الأصلي أولاً
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

        # التحديث مع الحفاظ على user_id الأصلي
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
            "user_id": existing_notification[0]  # إرجاع user_id الأصلي
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
    """حذف إشعار لمستخدم معين (للأدمن فقط)"""
    if admin_data["user_type"] != 1:
        raise HTTPException(
            status_code=403,
            detail="Only admins can delete user notifications"
        )

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # التحقق من وجود الإشعار وأنه من نوع user (is_admin=0)
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
    user_data: dict = Depends(auth_scheme)
):
    """الحصول على إشعاراتي (خاصة + عامة)"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # الإشعارات الخاصة + العامة
        cursor.execute(
            """SELECT id, message, is_admin, is_read, created_at 
            FROM notifications 
            WHERE user_id = ? OR (is_admin = 1 AND user_id IS NULL)
            ORDER BY created_at DESC""",
            (user_data["user_id"],)
        )

        notifications = []
        for row in cursor.fetchall():
            notifications.append({
                "id": row[0],
                "message": row[1],
                "is_admin": bool(row[2]),
                "is_read": bool(row[3]),
                "created_at": row[4],
                "type": "admin" if row[2] else "user"
            })

        return notifications
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch notifications: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.put("/user/notifications/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    user_data: dict = Depends(auth_scheme)
):
    """تحديد إشعار كمقروء"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # التحقق من ملكية الإشعار
        cursor.execute(
            """UPDATE notifications 
            SET is_read = 1 
            WHERE id = ? AND (user_id = ? OR (is_admin = 1 AND user_id IS NULL))""",
            (notification_id, user_data["user_id"])
        )
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404, detail="Notification not found")

        return {"success": True, "message": "Notification marked as read"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update notification: {str(e)}"
        )
    finally:
        if conn:
            conn.close()
