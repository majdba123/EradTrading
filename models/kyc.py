import sqlite3
from database.connection import get_db_connection

def create_kyc_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kyc_verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        document_type TEXT NOT NULL,
        document_number TEXT NOT NULL,
        front_image_url TEXT NOT NULL,
        back_image_url TEXT,
        selfie_image_url TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reviewed_at TIMESTAMP,
        reviewed_by INTEGER,
        rejection_reason TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (reviewed_by) REFERENCES users(id)
    )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_kyc_user ON kyc_verifications(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_kyc_status ON kyc_verifications(status)")
    
    conn.commit()
    conn.close()