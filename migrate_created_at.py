from app import create_app, db
from sqlalchemy import text
from datetime import datetime

app = create_app()

def add_column():
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                # Add column. SQLite doesn't support adding column with default CURRENT_TIMESTAMP easily in one go if not nullable
                # But here we set a default value for existing rows
                conn.execute(text("ALTER TABLE user ADD COLUMN created_at DATETIME"))
                
                # Update existing rows with current time
                current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                conn.execute(text(f"UPDATE user SET created_at = '{current_time}' WHERE created_at IS NULL"))
                
                conn.commit()
            print("Successfully added created_at column.")
        except Exception as e:
            print(f"Error adding column (might already exist): {e}")

if __name__ == "__main__":
    add_column()
