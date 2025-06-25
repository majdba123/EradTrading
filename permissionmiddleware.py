# security/permission_checker.py
from fastapi import HTTPException, Depends, Request, status
from database.connection import get_db_connection


async def check_permission(request: Request):
    print("Sss")

    """
    تحقق من صلاحية الوصول إلى الواجهة المطلوبة بناءً على المسار
    """
    conn = None
    try:
        # الحصول على المسار المطلوب
        path = request.url.path

        conn = get_db_connection()
        cursor = conn.cursor()

        # البحث عن الصلاحية المطابقة للمسار
        cursor.execute(
            """SELECT is_active FROM permissions 
            WHERE ? LIKE endpoint_path || '%'""",
            (path,)
        )
        permission = cursor.fetchone()

        if not permission:
            # إذا لم يتم العثور على الصلاحية، نعتبرها معطلة كإجراء أمان
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
