# security/permission_checker.py
from fastapi import HTTPException, Depends, Request, status
from database.connection import get_db_connection


async def check_permission(request: Request):
    print("Sss")

    """
    """
    conn = None
    try:
        path = request.url.path

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT is_active FROM permissions 
            WHERE ? LIKE endpoint_path || '%'""",
            (path,)
        )
        permission = cursor.fetchone()

        if not permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Endpoint not found in permissions system"
            )

        is_active = permission[0]

        if not is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This API endpoint is currently disabled"
            )

        return True

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Permission check failed: {str(e)}"
        )
    finally:
        if conn:
            conn.close()
