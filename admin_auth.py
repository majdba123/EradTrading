from fastapi import Request, HTTPException, status,Depends

from auth import auth_scheme
from database.connection import get_db_connection
from permissionmiddleware import check_permission
from auth import admin_scheme



async def admin_with_permission(request: Request, admin_data: dict = Depends(admin_scheme)):
    await check_permission(request)
    return admin_data


class AdminBearer:
    """للتحقق من أن المستخدم مدير"""

    async def __call__(self, request: Request):
        # التحقق من المصادقة الأساسية أولاً
        user_data = await auth_scheme(request)

        # التحقق من أن المستخدم مدير
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT 1 FROM users WHERE id = ? AND type = 1",
                (user_data["user_id"],)
            )

            if not cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="يجب أن تكون مديراً للوصول إلى هذه الصلاحية"
                )

            return user_data
        finally:
            if conn:
                conn.close()


admin_scheme = AdminBearer()
