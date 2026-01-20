from app import create_app, db, bcrypt
from app.models import User
import os

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False

with app.app_context():
    # Setup
    admin_pass = 'admin123'
    if not User.query.filter_by(email='temp_admin@test.com').first():
        admin = User(
            full_name='Temp Admin', 
            email='temp_admin@test.com', 
            password_hash=bcrypt.generate_password_hash(admin_pass).decode('utf-8'),
            role='admin',
            status='approved'
        )
        db.session.add(admin)
        db.session.commit()
    
    student = User.query.filter_by(email='student@test.com').first()
    if not student:
        student = User(
            full_name='Test Student',
            email='student@test.com',
            password_hash=bcrypt.generate_password_hash('oldpass').decode('utf-8'),
            role='student',
            status='approved'
        )
        db.session.add(student)
        db.session.commit()
    
    student_id = student.id
    
    # Simulate Request
    client = app.test_client()
    client.post('/login', data=dict(email='temp_admin@test.com', password=admin_pass), follow_redirects=True)
    
    new_pass = 'VerifiedPass123'
    print(f"Attempting to set password to: {new_pass}")
    resp = client.post(f'/admin/student/{student_id}/change_password', data=dict(new_password=new_pass), follow_redirects=True)
    
    # Check DB
    db.session.expire_all()
    updated_st = User.query.get(student_id)
    print(f"Plain Password in DB: {updated_st.plain_password}")
    
    if updated_st.plain_password == new_pass:
        print("SUCCESS")
    else:
        print("FAILURE")
        
    # Cleanup (optional, keeping users for manual check if needed)
    # db.session.delete(User.query.filter_by(email='temp_admin@test.com').first())
    # db.session.delete(User.query.filter_by(email='student@test.com').first())
    # db.session.commit()
