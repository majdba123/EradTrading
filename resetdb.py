# database/reset_database.py
import sqlite3
from database.connection import get_db_connection
from models.user import create_users_table
from models.managers import create_managers_table
from models.managers import create_manager_assignments_table
from models.mt5 import create_mt5_accounts_table
from seeder.user_seeder import seed_users


def reset_database():
    """
    Completely resets the database by:
    1. Dropping all existing tables
    2. Recreating the schema
    3. Seeding initial data

    WARNING: This will permanently delete all data in the database!
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. First disable all table operations
        # Temporarily disable foreign keys
        cursor.execute("PRAGMA foreign_keys = OFF")
        conn.commit()

        # 2. Get list of all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        all_tables = [table[0] for table in cursor.fetchall()]
        print("Existing tables before deletion:", all_tables)

        # 3. Explicitly drop all tables
        for table in all_tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                print(f"Successfully dropped table {table}")
                conn.commit()
            except Exception as e:
                print(f"Failed to drop table {table}: {str(e)}")
                conn.rollback()

        # 4. Recreate tables
        create_users_table()
        create_managers_table()
        create_manager_assignments_table()
        create_mt5_accounts_table()

        # 5. Re-enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.commit()

        # 6. Seed initial data
        seed_users()

        print("✅ Database reset completed successfully")

    except Exception as e:
        print(f"❌ Critical error occurred: {str(e)}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()
