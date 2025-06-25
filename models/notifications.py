# models/notifications.py
from database.connection import get_db_connection


def create_notifications_table():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT NULL,     
            message TEXT NOT NULL,
            is_admin BOOLEAN NOT NULL,       
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)

        # إنشاء فهرس لأداء أفضل
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_notifications_admin ON notifications(is_admin)")

        conn.commit()
    except Exception as e:
        print(f"Error creating notifications table: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()
    conn = None

