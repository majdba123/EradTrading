import sqlite3
import time
from contextlib import contextmanager
from database.connection import get_db_connection

# Add this context manager for database operations
@contextmanager
def db_connection():
    """Context manager for database connections with automatic retry"""
    max_retries = 5
    retry_delay = 0.2
    
    for attempt in range(max_retries):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA busy_timeout=5000")  # 5 second timeout
            yield conn
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            raise
        finally:
            if conn:
                conn.close()
    raise sqlite3.OperationalError("Failed to acquire database connection after retries")

def create_notifications_table():
    """Create the notifications table with WAL mode enabled"""
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER DEFAULT NULL,
                message TEXT NOT NULL,
                is_admin BOOLEAN NOT NULL,
                is_read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_admin ON notifications(is_admin)")
    except Exception as e:
        print(f"Error creating notifications table: {str(e)}")
        raise

def store_notification(user_id: int, message: str, is_admin: bool = False) -> int:
    """
    Stores a notification in the database with enhanced locking handling
    :param user_id: ID of the user to notify
    :param message: Notification message content
    :param is_admin: Whether this is an admin notification
    :return: ID of the created notification
    """
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO notifications (user_id, message, is_admin)
            VALUES (?, ?, ?)
            """, (user_id, message, is_admin))
            return cursor.lastrowid
    except Exception as e:
        print(f"Failed to store notification for user {user_id}: {str(e)}")
        raise