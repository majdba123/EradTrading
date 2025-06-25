# security/permission_checker.py
from fastapi import HTTPException, Depends,Request
from database.connection import get_db_connection
from auth import auth_scheme


async def check_permission(request: Request):
    """تحقق من حالة صلاحية الواجهة"""
    path = request.url.path
    
    # استثناء المسارات التي لا تحتاج تحقق
    if path in ['/docs', '/openapi.json']:
        return True
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT is_active FROM permissions 
            WHERE ? LIKE endpoint_path || '%' 
            ORDER BY LENGTH(endpoint_path) DESC LIMIT 1""",
            (path,)
        )
        permission = cursor.fetchone()
        
        if not permission:
            raise HTTPException(
                status_code=403,
                detail="Endpoint permission not configured"
            )
            
        if not permission[0]:
            raise HTTPException(
                status_code=403,
                detail="This API endpoint is currently disabled"
            )
            
        return True
    finally:
        conn.close()