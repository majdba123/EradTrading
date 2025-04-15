# seeder/user_seeder.py
from database.connection import get_db_connection


def seed_users():
    conn = get_db_connection()
    cursor = conn.cursor()

    # بيانات المستخدم الافتراضي
    default_user = {
        'phone': '0123456789',
        'passcode': '1234',
        'status': 'approved',
        'type': 1
    }

    try:
        cursor.execute("""
        INSERT INTO users (phone, passcode, status, type)
        VALUES (?, ?, ?, ?)
        """, (default_user['phone'], default_user['passcode'],
              default_user['status'], default_user['type']))

        conn.commit()
        print("User seeded successfully!")
    except sqlite3.IntegrityError:
        print("User already exists in the database.")
    finally:
        conn.close()
