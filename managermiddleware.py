from fastapi import Request, HTTPException, status
from auth import auth_scheme
from database.connection import get_db_connection


class AdminBearer:
    """Verify that the user is an admin"""

    async def __call__(self, request: Request):
        # First verify basic authentication
        user_data = await auth_scheme(request)

        # Verify the user is an admin
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT 1 FROM users WHERE id = ? AND type = 2",
                (user_data["user_id"],)
            )

            if not cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You must be an admin to access this permission"
                )

            return user_data
        finally:
            if conn:
                conn.close()


admin_scheme = AdminBearer()
