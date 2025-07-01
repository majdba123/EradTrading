from fastapi import Request, HTTPException, status, Depends
from auth import auth_scheme, admin_scheme
from database.connection import get_db_connection
from permissionmiddleware import check_permission


async def admin_with_permission(request: Request, admin_data: dict = Depends(admin_scheme)):
    """
    Verify admin status and check specific permissions

    Args:
        request: FastAPI request object
        admin_data: Authenticated admin data from dependency

    Returns:
        dict: Admin user data if authorized
    """
    await check_permission(request)
    return admin_data


class AdminBearer:
    """Verifies that the user is an admin"""

    async def __call__(self, request: Request):
        """
        Authentication check for admin users

        Args:
            request: FastAPI request object

        Returns:
            dict: User data if admin

        Raises:
            HTTPException: 403 if user is not an admin
        """
        # First verify basic authentication
        user_data = await auth_scheme(request)

        # Verify the user is an admin
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
                    detail="Admin privileges required to access this resource"
                )

            return user_data
        finally:
            if conn:
                conn.close()


admin_scheme = AdminBearer()
