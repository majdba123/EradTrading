# database/reset_database.py
import sqlite3
from database.connection import get_db_connection
from models.user import create_users_table
from models.managers import create_managers_table
from models.managers import create_manager_assignments_table
from models.mt5 import create_mt5_accounts_table
from seeder.user_seeder import seed_users

def reset_database():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. إيقاف جميع العمليات على الجداول أولاً
        cursor.execute("PRAGMA foreign_keys = OFF")  # تعطيل المفاتيح الأجنبية مؤقتاً
        conn.commit()
        
        # 2. الحصول على قائمة جميع الجداول
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        all_tables = [table[0] for table in cursor.fetchall()]
        print("الجداول الموجودة قبل الحذف:", all_tables)
        
        # 3. حذف جميع الجداول بشكل صريح
        for table in all_tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                print(f"تم حذف جدول {table} بنجاح")
                conn.commit()
            except Exception as e:
                print(f"فشل في حذف جدول {table}: {str(e)}")
                conn.rollback()
        
        # 4. إعادة إنشاء الجداول
        create_users_table()
        create_managers_table()
        create_manager_assignments_table()
        create_mt5_accounts_table()
        
        # 5. إعادة تفعيل المفاتيح الأجنبية
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        
        # 6. إضافة البيانات الأولية
        seed_users()
        
        print("✅ تم إعادة تعيين قاعدة البيانات بالكامل بنجاح")
        
    except Exception as e:
        print(f"❌ حدث خطأ جسيم: {str(e)}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()