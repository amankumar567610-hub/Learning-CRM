from app import create_app, db
from sqlalchemy import text

app = create_app()

def add_column():
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE user ADD COLUMN profile_image VARCHAR(150) DEFAULT 'default_avatar.png'"))
                conn.commit()
            print("Successfully added profile_image column.")
        except Exception as e:
            print(f"Error adding column (might already exist): {e}")

if __name__ == "__main__":
    add_column()
