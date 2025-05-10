import sqlite3
from database.connection import get_db_connection


def create_users_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL UNIQUE,
        passcode TEXT NOT NULL,
        first_name TEXT,
        last_name TEXT,
        status TEXT DEFAULT 'pending',  -- pending, approved, rejected
        type INTEGER DEFAULT 0,        -- 0: مستخدم عادي، 1: مسؤول
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()