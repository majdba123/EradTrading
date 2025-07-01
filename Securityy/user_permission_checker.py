# security/user_permission_checker.py
from fastapi import HTTPException, status,Depends
from database.connection import get_db_connection
from auth import auth_scheme



class UserPermissionChecker:
    def __init__(self, endpoint_name: str):
        self.endpoint_name = endpoint_name

    async def __call__(self, user_data: dict = Depends(auth_scheme)):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id FROM permissions WHERE endpoint_name = ?",
                (self.endpoint_name,)
            )
            permission = cursor.fetchone()

            if not permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Permission not found"
                )

            permission_id = permission[0]

            cursor.execute(
                """SELECT 1 FROM user_deny_permissions 
                WHERE user_id = ? AND permission_id = ?""",
                (user_data["user_id"], permission_id)
            )

            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are blocked from accessing this functionality"
                )

            return True
        finally:
            if conn:
                conn.close()
