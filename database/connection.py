import sqlite3  # إضافة استيراد مكتبة sqlite3


def get_db_connection():
    try:
        conn = sqlite3.connect("Erad.db", check_same_thread=False)
        return conn
    except sqlite3.Error as e:
        raise Exception(f"Failed to connect to database: {e}")
