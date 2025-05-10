# database/reset_database.py
import sqlite3
from database.connection import get_db_connection
from models.user import create_users_table
from models.managers import create_managers_table
from models.managers import create_manager_assignments_table
from models.mt5 import create_mt5_accounts_table 

from seeder.user_seeder import seed_users  # استيراد دالة السيدر


def reset_database():
    conn = get_db_connection()
    cursor = conn.cursor()

    # حذف جميع الجداول
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute("DROP TABLE IF EXISTS managers")
    cursor.execute("DROP TABLE IF EXISTS mt5")


    # إعادة إنشاء الجداول
    create_users_table()
    create_managers_table()
    create_manager_assignments_table()
    create_mt5_accounts_table()
    # تشغيل السيدر لإضافة المستخدم الافتراضي
    seed_users()

    conn.commit()
    print("Database has been reset and seeded successfully!")
    conn.close()
