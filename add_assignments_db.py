from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        with db.engine.connect() as conn:
            # Check if tables exist
            tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';")).fetchall()
            table_names = [t[0] for t in tables]
            
            if 'assignment' not in table_names:
                print("Creating 'assignment' table...")
                conn.execute(text("""
                    CREATE TABLE assignment (
                        id INTEGER NOT NULL, 
                        lesson_id INTEGER NOT NULL, 
                        instructions TEXT NOT NULL, 
                        max_score INTEGER, 
                        created_at DATETIME, 
                        PRIMARY KEY (id), 
                        FOREIGN KEY(lesson_id) REFERENCES lesson (id)
                    );
                """))
                print("'assignment' table created.")
            else:
                print("'assignment' table already exists.")
                
            if 'submission' not in table_names:
                print("Creating 'submission' table...")
                conn.execute(text("""
                    CREATE TABLE submission (
                        id INTEGER NOT NULL, 
                        user_id INTEGER NOT NULL, 
                        assignment_id INTEGER NOT NULL, 
                        file_path VARCHAR(300) NOT NULL, 
                        grade INTEGER, 
                        feedback TEXT, 
                        submitted_at DATETIME, 
                        PRIMARY KEY (id), 
                        FOREIGN KEY(user_id) REFERENCES user (id), 
                        FOREIGN KEY(assignment_id) REFERENCES assignment (id)
                    );
                """))
                print("'submission' table created.")
            else:
                print("'submission' table already exists.")
            
            conn.commit()
            print("Database migration completed successfully.")
                
    except Exception as e:
        print(f"Error during migration: {e}")
