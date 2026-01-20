from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Adding 'answers' column to 'quiz_result' table...")
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE quiz_result ADD COLUMN answers TEXT"))
            conn.commit()
        print("Column added successfully.")
    except Exception as e:
        print(f"Error (column might already exist): {e}")
