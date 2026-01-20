from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False, default='Unknown')
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    plain_password = db.Column(db.String(128), nullable=True) # Storing for admin reference as requested
    profile_image = db.Column(db.String(300), nullable=True, default='default_avatar.png')
    role = db.Column(db.String(20), nullable=False, default='student') # admin, student
    status = db.Column(db.String(20), nullable=False, default='pending') # pending, approved, rejected
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    enrolled_courses = db.relationship('Course', secondary='enrollments', backref=db.backref('students', lazy=True))

    def __repr__(self):
        return f"User('{self.email}', '{self.role}', '{self.status}')"

enrollments = db.Table('enrollments',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('course_id', db.Integer, db.ForeignKey('course.id'), primary_key=True)
)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    courses = db.relationship('Course', backref='category', lazy=True)

    def __repr__(self):
        return f"Category('{self.name}')"

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    thumbnail_url = db.Column(db.String(200), nullable=True) # URL to image
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    modules = db.relationship('Module', backref='course', lazy=True, order_by='Module.order_index')

    def __repr__(self):
        return f"Course('{self.title}')"

class Module(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    order_index = db.Column(db.Integer, nullable=False, default=0)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    lessons = db.relationship('Lesson', backref='module', lazy=True, order_by='Lesson.order_index')

    def __repr__(self):
        return f"Module('{self.title}')"

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    video_url = db.Column(db.String(200), nullable=True)
    content = db.Column(db.Text, nullable=True)
    order_index = db.Column(db.Integer, nullable=False, default=0)
    module_id = db.Column(db.Integer, db.ForeignKey('module.id'), nullable=False)

    def __repr__(self):
        return f"Lesson('{self.title}')"

class LessonProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Ensure a user has only one progress record per lesson
    __table_args__ = (db.UniqueConstraint('user_id', 'lesson_id', name='unique_user_lesson_progress'),)

    def __repr__(self):
        return f"Progress(User: {self.user_id}, Lesson: {self.lesson_id}, Completed: {self.is_completed})"

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Access quiz via lesson.quiz
    lesson = db.relationship('Lesson', backref=db.backref('quiz', uselist=False, cascade="all, delete-orphan"))
    questions = db.relationship('Question', backref='quiz', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"Quiz('{self.title}')"

    @property
    def questions_list(self):
        return [q.to_dict for q in self.questions]


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    # Storing options as JSON string: '["Option A", "Option B", ...]'
    options = db.Column(db.Text, nullable=False) 
    # Storing correct answer index: 0, 1, 2, etc.
    correct_option = db.Column(db.Integer, nullable=False)

    @property
    def to_dict(self):
        return {
            'text': self.question_text,
            'options': self.options, 
            'correct_option': self.correct_option
        }

class QuizResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False) # Percentage or raw score
    passed = db.Column(db.Boolean, default=False)
    answers = db.Column(db.Text, nullable=True) # Storing user answers as JSON: {question_id: option_index}
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    max_score = db.Column(db.Integer, default=100)
    resource_path = db.Column(db.String(300), nullable=True) # Path to attached resource
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # One-to-One with Lesson (access via lesson.assignment)
    lesson = db.relationship('Lesson', backref=db.backref('assignment', uselist=False, cascade="all, delete-orphan"))
    submissions = db.relationship('Submission', backref='assignment', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"Assignment(Lesson: {self.lesson_id})"

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    file_path = db.Column(db.String(300), nullable=False) # Path to uploaded file
    grade = db.Column(db.Integer, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # User relationship
    student = db.relationship('User', backref='submissions')

    def __repr__(self):
        return f"Submission(User: {self.user_id}, Assignment: {self.assignment_id})"

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    link = db.Column(db.String(300), nullable=True) # Link to the relevant page (e.g., submission review)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"Notification('{self.message}')"
