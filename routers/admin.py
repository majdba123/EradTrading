import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status, Query
from database.connection import get_db_connection
from schemas.users import ManagerCreate, ManagerFilter
from admin_auth import admin_scheme
from typing import Optional
from pydantic import BaseModel

router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)

@router.post("/add-manager")
def add_manager(
    manager_data: ManagerCreate,
    admin_data: dict = Depends(admin_scheme)
):
    """إضافة مدير جديد مع إنشاء حساب مستخدم له"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # بدء المعاملة
        cursor.execute("BEGIN TRANSACTION")

        # 1. إنشاء حساب المستخدم (مدير)
        cursor.execute(
            """INSERT INTO users (phone, passcode, type, status)
               VALUES (?, ?, 1, 'active')""",
            (manager_data.phone, manager_data.passcode)
        )
        user_id = cursor.lastrowid

        # 2. إنشاء سجل المدير
        cursor.execute(
            """INSERT INTO managers (user_id, name)
               VALUES (?, ?)""",
            (user_id, manager_data.name)
        )

        # تأكيد المعاملة
        conn.commit()

        return {
            "success": True,
            "message": "تمت إضافة المدير بنجاح",
            "user_id": user_id,
            "phone": manager_data.phone,
            "name": manager_data.name
        }

    except sqlite3.IntegrityError as e:
        conn.rollback()
        if "UNIQUE constraint failed: users.phone" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="رقم الهاتف مسجل مسبقاً"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"خطأ في قاعدة البيانات: {str(e)}"
        )
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"فشل في إضافة المدير: {str(e)}"
        )
    finally:
        if conn:
            conn.close()

@router.get("/managers")
def get_all_managers(
    admin_data: dict = Depends(admin_scheme),
    page: int = Query(1, gt=0, description="رقم الصفحة"),
    per_page: int = Query(10, gt=0, le=100, description="عدد العناصر في الصفحة"),
    name: Optional[str] = Query(None, description="تصفية حسب الاسم"),
    phone: Optional[str] = Query(None, description="تصفية حسب رقم الهاتف"),
    status: Optional[str] = Query(None, description="تصفية حسب الحالة")
):
    """الحصول على قائمة جميع المديرين مع الترقيم الصفحي والتصفية والترتيب"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # بناء استعلام SQL مع التصفية
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

        # إضافة عوامل التصفية إذا وجدت
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

        # إضافة الترتيب من الأحدث
        base_query += " ORDER BY m.created_at DESC"

        # حساب الإزاحة للترقيم الصفحي
        offset = (page - 1) * per_page

        # استعلام العد الكلي
        count_query = "SELECT COUNT(*) FROM (" + base_query + ")"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # استعلام البيانات مع الترقيم الصفحي
        paginated_query = base_query + " LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        cursor.execute(paginated_query, params)

        # تحويل النتائج
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
            detail=f"فشل في جلب بيانات المديرين: {str(e)}"
        )
    finally:
        if conn:
            conn.close()

@router.post("/managers/filter")
def filter_managers(
    filter_data: ManagerFilter,
    admin_data: dict = Depends(admin_scheme)
):
    """الحصول على قائمة المديرين مع التصفية باستخدام JSON في Body"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # بناء استعلام SQL مع التصفية
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

        # إضافة عوامل التصفية إذا وجدت
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

        # إضافة الترتيب من الأحدث
        base_query += " ORDER BY m.created_at DESC"

        # حساب الإزاحة للترقيم الصفحي
        offset = (filter_data.page - 1) * filter_data.per_page

        # استعلام العد الكلي
        count_query = "SELECT COUNT(*) FROM (" + base_query + ")"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # استعلام البيانات مع الترقيم الصفحي
        paginated_query = base_query + " LIMIT ? OFFSET ?"
        params.extend([filter_data.per_page, offset])
        cursor.execute(paginated_query, params)

        # تحويل النتائج
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
            detail=f"فشل في جلب بيانات المديرين: {str(e)}"
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
    """الحصول على جميع المديرين مع المستخدمين المرتبطين بهم"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # جلب جميع المديرين
        cursor.execute("""
            SELECT m.id, m.name, u.phone, u.status
            FROM managers m
            JOIN users u ON m.user_id = u.id
            ORDER BY m.name
        """)
        managers = cursor.fetchall()

        result = []
        for manager in managers:
            # جلب المستخدمين المرتبطين بكل مدير
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
            detail=f"فشل في جلب البيانات: {str(e)}"
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
    """ربط مستخدم بمدير مع التحقق من عدم وجود مدير آخر"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # التحقق من وجود المدير
        cursor.execute("SELECT id FROM managers WHERE id = ?", (manager_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="المدير غير موجود"
            )

        # التحقق من وجود المستخدم
        cursor.execute("SELECT id, type FROM users WHERE id = ?", (request.user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="المستخدم غير موجود"
            )

        # التحقق من أن المستخدم ليس مديراً
        if user[1] == 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="لا يمكن ربط مدير بمدير آخر"
            )

        # التحقق من أن المستخدم ليس مرتبطاً بمدير آخر
        cursor.execute("""
            SELECT manager_id FROM manager_assignments 
            WHERE user_id = ?
        """, (request.user_id,))
        existing_assignment = cursor.fetchone()
        
        if existing_assignment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"المستخدم مرتبط بالفعل بمدير آخر (ID: {existing_assignment[0]})"
            )

        # ربط المستخدم بالمدير
        cursor.execute("""
            INSERT INTO manager_assignments (manager_id, user_id)
            VALUES (?, ?)
        """, (manager_id, request.user_id))

        conn.commit()
        return {
            "success": True,
            "message": "تم ربط المستخدم بالمدير بنجاح",
            "manager_id": manager_id,
            "user_id": request.user_id
        }

    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"خطأ في قاعدة البيانات: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"فشل في ربط المستخدم: {str(e)}"
        )
    finally:
        if conn:
            conn.close()

@router.delete("/delete-manager/{manager_id}")
def delete_manager(
    manager_id: int,
    admin_data: dict = Depends(admin_scheme)
):
    """حذف مدير مع التحقق من عدم وجود مستخدمين مرتبطين"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # بدء المعاملة
        cursor.execute("BEGIN TRANSACTION")

        # 1. التحقق من وجود المدير وعدد المستخدمين المرتبطين
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
                detail="المدير غير موجود"
            )

        user_id = manager_info[1]
        assigned_users_count = manager_info[2]

        # 2. رفض الحذف إذا كان لديه مستخدمين مرتبطين
        if assigned_users_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"لا يمكن حذف المدير لديه {assigned_users_count} مستخدم مرتبط. يرجى إلغاء ربطهم أولاً"
            )

        # 3. حذف سجل المدير
        cursor.execute("""
            DELETE FROM managers 
            WHERE id = ?
        """, (manager_id,))

        # 4. تحديث نوع المستخدم إلى غير مدير
        cursor.execute("""
            UPDATE users 
            SET type = 0 
            WHERE id = ? AND type = 1
        """, (user_id,))

        conn.commit()
        
        return {
            "success": True,
            "message": "تم حذف المدير بنجاح",
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
            detail=f"فشل في حذف المدير: {str(e)}"
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
    """فك ربط مستخدم من مدير"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # التحقق من وجود العلاقة
        cursor.execute("""
            SELECT 1 FROM manager_assignments
            WHERE manager_id = ? AND user_id = ?
        """, (request.manager_id, request.user_id))
        
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="لا يوجد ارتباط بين المدير والمستخدم"
            )

        # فك الربط
        cursor.execute("""
            DELETE FROM manager_assignments
            WHERE manager_id = ? AND user_id = ?
        """, (request.manager_id, request.user_id))

        conn.commit()
        
        return {
            "success": True,
            "message": "تم فك ربط المستخدم من المدير بنجاح",
            "manager_id": request.manager_id,
            "user_id": request.user_id
        }

    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"فشل في فك الربط: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.get("/manager-users/{manager_id}")
def get_manager_users(
    manager_id: int,
    admin_data: dict = Depends(admin_scheme)
):
    """الحصول على جميع المستخدمين المرتبطين بمدير معين"""
    conn = None
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row  # هذا السطر مهم للتحويل إلى قاموس
        cursor = conn.cursor()

        # التحقق من وجود المدير أولاً
        cursor.execute("SELECT id FROM managers WHERE id = ?", (manager_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="المدير غير موجود"
            )

        # جلب المستخدمين المرتبطين
        cursor.execute("""
            SELECT u.id, u.phone, u.status
            FROM manager_assignments ma
            JOIN users u ON ma.user_id = u.id
            WHERE ma.manager_id = ?
        """, (manager_id,))
        
        # تحويل النتائج إلى قواميس
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
            detail=f"فشل في جلب البيانات: {str(e)}"
        )
    finally:
        if conn:
            conn.close()