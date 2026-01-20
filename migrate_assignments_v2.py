from app import create_app,db
import sqlite3

app = create_app()

def migrate():
    with app.app_context():
        # Add resource_path column to assignment table
        try:
            with sqlite3.connect('instance/site.db') as conn:
                cursor = conn.cursor()
                cursor.execute("ALTER TABLE assignment ADD COLUMN resource_path TEXT")
                conn.commit()
                print("Added resource_path to assignment table.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    migrate()
