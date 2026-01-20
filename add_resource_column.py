import sqlite3
import os

# Database file path
DB_PATH = 'instance/site.db'

def migrate_db():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(assignment)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'resource_path' not in columns:
            print("Adding 'resource_path' column to 'assignment' table...")
            cursor.execute("ALTER TABLE assignment ADD COLUMN resource_path VARCHAR(300)")
            conn.commit()
            print("Migration successful: Column added.")
        else:
            print("Column 'resource_path' already exists. No action needed.")
            
        conn.close()
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    migrate_db()
