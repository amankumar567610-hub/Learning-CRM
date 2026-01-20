from app import create_app, db, bcrypt
from app.models import User

app = create_app()

with app.app_context():
    db.create_all()
    
    if not User.query.filter_by(email='admin@course.com').first():
        hashed_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
        admin = User(
            email='admin@course.com', 
            password_hash=hashed_password, 
            role='admin',
            status='approved',
            full_name='System Admin'
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created: admin@course.com / admin123")
    else:
        print("Admin user already exists.")
