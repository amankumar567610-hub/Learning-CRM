import unittest
from app import create_app, db, bcrypt
from app.models import User

class TestPasswordChange(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing ease
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Setup secure admin
        self.admin_pass = 'admin123'
        self.admin = User(
            full_name='Temp Admin',
            email='temp_admin@test.com',
            password_hash=bcrypt.generate_password_hash(self.admin_pass).decode('utf-8'),
            role='admin',
            status='approved'
        )
        # Setup student
        self.student = User(
            full_name='Test Student',
            email='student@test.com',
            password_hash=bcrypt.generate_password_hash('oldpass').decode('utf-8'),
            role='student',
            status='approved'
        )
        db.session.add(self.admin)
        db.session.add(self.student)
        db.session.commit()
        self.student_id = self.student.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_change_password_saves_plain(self):
        # Login
        self.client.post('/login', data=dict(
            email='temp_admin@test.com',
            password=self.admin_pass
        ), follow_redirects=True)

        # Change Password
        new_pass = 'super_secure_new_pass'
        resp = self.client.post(f'/admin/student/{self.student_id}/change_password', data=dict(
            new_password=new_pass
        ), follow_redirects=True)
        
        # Verify
        updated_student = User.query.get(self.student_id)
        print(f"\nStatus Code: {resp.status_code}")
        print(f"Plain Password in DB: {updated_student.plain_password}")
        
        if updated_student.plain_password == new_pass:
            print("SUCCESS: Plain password saved.")
        else:
            print("FAILURE: Plain password NOT saved.")

if __name__ == '__main__':
    unittest.main()
