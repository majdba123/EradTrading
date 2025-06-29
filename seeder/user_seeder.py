# seeder/user_seeder.py
from database.connection import get_db_connection
import sqlite3
from security import cipher  # استيراد كائن التشفير


def seed_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    x= cipher.encrypt_password("123456789")
    # بيانات المستخدم الافتراضي
    default_user = {
        'phone': '0123456789',
        'passcode': '123456',
        'status': 'approved',
        'type': 1,
        'password': x,
    }

    try: 
        cursor.execute("""
        INSERT INTO users (phone, passcode, status, type,password)
        VALUES (?, ?, ?, ?,?)
        """, (default_user['phone'], default_user['passcode'],
              default_user['status'], default_user['type'],default_user['password']))

        conn.commit()
        print("User seeded successfully!")
    except sqlite3.IntegrityError:
        print("User already exists in the database.")
    finally:
        conn.close()
