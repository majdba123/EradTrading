import sqlite3
from database.connection import get_db_connection
from models.user import create_users_table


def reset_database():
    conn = get_db_connection()
    cursor = conn.cursor()

    # حذف جميع الجداول
    cursor.execute("DROP TABLE IF EXISTS users")

    # إعادة إنشاء الجداول
    create_users_table()

    conn.commit()
    print("Database has been reset successfully!")
