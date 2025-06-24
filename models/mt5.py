from database.connection import get_db_connection

def create_mt5_accounts_table():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_mt5_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            mt5_login_id INTEGER NOT NULL UNIQUE,
            mt5_password TEXT NOT NULL,
            mt5_investor_password TEXT NOT NULL,
            account_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',  -- pending, approved, rejected, banned

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """)
        
        conn.commit()
    except Exception as e:
        print(f"Error creating MT5 accounts table: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()