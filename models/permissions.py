# models/permissions.py
from database.connection import get_db_connection


def create_permissions_table():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            required_permission TEXT,
            endpoint_name TEXT NOT NULL UNIQUE,
            endpoint_path TEXT NOT NULL UNIQUE,
            is_active INTEGER DEFAULT 1,  -- 1 for active, 0 for inactive
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.commit()
    except Exception as e:
        print(f"Error creating Permissions table: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()


def create_user_permissions_tables():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_deny_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            permission_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (permission_id) REFERENCES permissions(id),
            UNIQUE (user_id, permission_id)
        )
        """)

        conn.commit()
    except Exception as e:
        print(f"Error creating user permissions tables: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()
