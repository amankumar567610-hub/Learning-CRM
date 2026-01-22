from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from werkzeug.utils import secure_filename
import os
from flask_login import login_required, current_user
from app import db, bcrypt
from app.models import User

admin_bp = Blueprint('admin_bp', __name__, url_prefix='/admin')

@admin_bp.before_request
@login_required
def require_admin():
    if current_user.role != 'admin':
        flash('Access Denied', 'danger')
        return redirect(url_for('main.index'))

@admin_bp.route('/students')
def students():
    pending_students = User.query.filter_by(role='student', status='pending').all()
    approved_students = User.query.filter_by(role='student', status='approved').all()
    rejected_students = User.query.filter_by(role='student', status='rejected').all()
    courses = Course.query.all()
    return render_template('admin/students.html', pending=pending_students, approved=approved_students, rejected=rejected_students, courses=courses)

@admin_bp.route('/student/<int:user_id>/approve', methods=['POST'])
def approve_student(user_id):
    user = User.query.get_or_404(user_id)
    user.status = 'approved'
    db.session.commit()
    flash(f'Student {user.full_name} approved!', 'success')
    return redirect(url_for('admin_bp.students'))

@admin_bp.route('/student/<int:user_id>/reject', methods=['POST'])
def reject_student(user_id):
    user = User.query.get_or_404(user_id)
    user.status = 'rejected'
    db.session.commit()
    flash(f'Student {user.full_name} rejected.', 'warning')
    return redirect(url_for('admin_bp.students'))

from app.models import Category, Course

# --- Categories ---
@admin_bp.route('/categories', methods=['GET', 'POST'])
def categories():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            category = Category(name=name)
            try:
                db.session.add(category)
                db.session.commit()
                flash('Category added!', 'success')
            except Exception:
                db.session.rollback()
                flash(f'Category "{name}" already exists.', 'warning')
        else:
             flash('Category name is required.', 'danger')
        return redirect(url_for('admin_bp.categories'))
        
    categories = Category.query.all()
    return render_template('admin/categories.html', categories=categories)

@admin_bp.route('/category/<int:category_id>/delete', methods=['POST'])
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    
    try:
        # Recursive deletion of courses in this category
        courses = Course.query.filter_by(category_id=category.id).all()
        for course in courses:
            # Reusing the logic from delete_course would be ideal, but for now copying the critical parts
            # to ensure clean cascade.
            # Ideally, refactor delete_course logic into a helper function later.
            
            for module in course.modules:
                for lesson in module.lessons:
                    # 1. Delete Progress
                    from app.models import LessonProgress, QuizResult, Submission
                    LessonProgress.query.filter_by(lesson_id=lesson.id).delete()
                    
                    # 2. Delete Quiz & Results
                    if lesson.quiz:
                        QuizResult.query.filter_by(quiz_id=lesson.quiz.id).delete()
            
                    # 3. Delete Assignment & Submissions
                    if lesson.assignment:
                        Submission.query.filter_by(assignment_id=lesson.assignment.id).delete()
                        db.session.delete(lesson.assignment)
                    
                    # 4. Delete Lesson
                    db.session.delete(lesson)
                
                # 5. Delete Module
                db.session.delete(module)
            
            # Clear enrollments
            course.students = []
            db.session.delete(course)

        db.session.delete(category)
        db.session.commit()
        flash(f'Category "{category.name}" and all its courses were successfully deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        print(e)
        flash('An error occurred while deleting the category.', 'danger')

    return redirect(url_for('admin_bp.categories'))

# --- Courses ---
@admin_bp.route('/courses', methods=['GET', 'POST'])
def courses():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category_id = request.form.get('category_id')
        thumbnail_url = request.form.get('thumbnail_url')
        
        # Handle Image Upload
        if 'thumbnail_file' in request.files:
            file = request.files['thumbnail_file']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                # Ensure unique filename to avoid overwrites (timestamp prefix)
                from datetime import datetime
                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                filename = f"{timestamp}_{filename}"
                
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                try:
                    file.save(file_path)
                    thumbnail_url = filename # Store filename, easy to distinguish from full URL
                except Exception as e:
                    print(f"Error saving course thumbnail: {e}")
                    flash('Error uploading image', 'warning')

        
        if title and description and category_id:
            course = Course(
                title=title, 
                description=description, 
                category_id=category_id,
                thumbnail_url=thumbnail_url
            )
            db.session.add(course)
            db.session.commit()
            flash('Course created!', 'success')
        else:
            flash('All fields are required.', 'danger')
        return redirect(url_for('admin_bp.courses'))

    courses = Course.query.all()
    categories = Category.query.all()
    return render_template('admin/courses.html', courses=courses, categories=categories)

@admin_bp.route('/course/<int:course_id>/delete', methods=['POST'])
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    
    try:
        # Manual Cascade Deletion
        for module in course.modules:
            for lesson in module.lessons:
                # 1. Delete Progress
                from app.models import LessonProgress, QuizResult, Submission
                LessonProgress.query.filter_by(lesson_id=lesson.id).delete()
                
                # 2. Delete Quiz & Results
                if lesson.quiz:
                    QuizResult.query.filter_by(quiz_id=lesson.quiz.id).delete()
                    # Questions cascade deleted by model if quiz deleted, but lesson relationship handles quiz orphan?
                    # Model says: lesson = db.relationship('Lesson', backref=db.backref('quiz', uselist=False, cascade="all, delete-orphan"))
                    # But quiz is parent of questions with cascade.
                    pass 

                # 3. Delete Assignment & Submissions
                if lesson.assignment:
                    Submission.query.filter_by(assignment_id=lesson.assignment.id).delete()
                    db.session.delete(lesson.assignment)
                
                # 4. Delete Lesson
                db.session.delete(lesson)
            
            # 5. Delete Module
            db.session.delete(module)

        # 6. Delete Enrollments (Many-to-Many not automatically handled unless cascade set?)
        # db.session.delete(course) handles relationships in association table if configured, 
        # but let's clear it explicitly if needed.
        course.students = [] 

        db.session.delete(course)
        db.session.commit()
        flash(f'Course "{course.title}" was successfully deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        print(e)
        flash('An error occurred while deleting the course.', 'danger')

    return redirect(url_for('admin_bp.courses'))

# --- Course Content (Modules & Lessons) ---
from app.models import Module, Lesson

@admin_bp.route('/course/<int:course_id>/content')
def course_content(course_id):
    course = Course.query.get_or_404(course_id)
    return render_template('admin/course_content.html', course=course)

@admin_bp.route('/course/<int:course_id>/add_module', methods=['POST'])
def add_module(course_id):
    course = Course.query.get_or_404(course_id)
    title = request.form.get('title')
    
    if title:
        # Simple auto-increment order
        count = Module.query.filter_by(course_id=course_id).count()
        module = Module(title=title, course_id=course_id, order_index=count)
        db.session.add(module)
        db.session.commit()
        flash('Module added!', 'success')
    else:
        flash('Module title required', 'danger')
        
    return redirect(url_for('admin_bp.course_content', course_id=course_id))

@admin_bp.route('/module/<int:module_id>/add_lesson', methods=['POST'])
def add_lesson(module_id):
    module = Module.query.get_or_404(module_id)
    title = request.form.get('title')
    video_url = request.form.get('video_url')
    
    if title:
        count = Lesson.query.filter_by(module_id=module_id).count()
        lesson = Lesson(
            title=title, 
            video_url=video_url, 
            module_id=module_id, 
            order_index=count
        )
        db.session.add(lesson)
        db.session.commit()
        flash('Lesson added!', 'success')
    else:
        flash('Lesson title required', 'danger')
        
    return redirect(url_for('admin_bp.course_content', course_id=module.course_id))

@admin_bp.route('/student/<int:user_id>/enroll', methods=['POST'])
def enroll_student(user_id):
    user = User.query.get_or_404(user_id)
    course_id = request.form.get('course_id')
    
    if course_id:
        course = Course.query.get(course_id)
        if course:
            if course not in user.enrolled_courses:
                user.enrolled_courses.append(course)
                db.session.commit()
                flash(f'Enrolled {user.full_name} in {course.title}', 'success')
            else:
                flash('Student already enrolled.', 'warning')
    
    return redirect(url_for('admin_bp.students'))

@admin_bp.route('/student/<int:user_id>/unenroll/<int:course_id>', methods=['POST'])
def unenroll_student(user_id, course_id):
    user = User.query.get_or_404(user_id)
    course = Course.query.get_or_404(course_id)
    
    if course in user.enrolled_courses:
        user.enrolled_courses.remove(course)
        db.session.commit()
        flash(f'Removed {user.full_name} from {course.title}', 'success')
    else:
        flash('Student was not enrolled in this course.', 'warning')
        
    return redirect(url_for('admin_bp.students'))

# --- Quizzes ---
from app.models import Quiz, Question
import json
import re

@admin_bp.route('/lesson/<int:lesson_id>/add_quiz', methods=['GET', 'POST'])
def add_quiz(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    
    if request.method == 'POST':
        title = request.form.get('title')
        
        if title:
            # Check if quiz exists for this lesson
            quiz = Quiz.query.filter_by(lesson_id=lesson_id).first()
            
            if quiz:
                quiz.title = title
                # Clear existing questions to replace them (simplest approach for full form submission)
                for q in quiz.questions:
                    db.session.delete(q)
            else:
                quiz = Quiz(title=title, lesson_id=lesson_id)
                db.session.add(quiz)
            
            db.session.commit() # Commit changes/creation
            
            # Parse questions from form data
            # Form format: questions[1][text], questions[1][options][], questions[1][correct]
            
            # Find all unique indices (the '1' in questions[1]...)
            indices = set()
            for key in request.form:
                match = re.search(r'questions\[(\d+)\]', key)
                if match:
                    indices.add(int(match.group(1)))
            
            for index in sorted(indices):
                q_text = request.form.get(f'questions[{index}][text]')
                q_options = request.form.getlist(f'questions[{index}][options][]')
                q_correct = request.form.get(f'questions[{index}][correct]')
                
                if q_text and len(q_options) >= 2 and q_correct is not None:
                    # Filter out empty options if any (optional, but good for cleanliness)
                    # q_options = [opt for opt in q_options if opt.strip()]
                    
                    question = Question(
                        quiz_id=quiz.id,
                        question_text=q_text,
                        options=json.dumps(q_options),
                        correct_option=int(q_correct)
                    )
                    db.session.add(question)
            
            db.session.commit()
            flash('Quiz saved successfully!', 'success')
            return redirect(url_for('admin_bp.course_content', course_id=lesson.module.course.id))
            
    # Pre-populate if quiz exists
    quiz = Quiz.query.filter_by(lesson_id=lesson_id).first()
    existing_questions = []
    if quiz:
        for q in quiz.questions:
            existing_questions.append({
                'text': q.question_text,
                'options': json.loads(q.options),
                'correct': q.correct_option
            })
            
    return render_template('admin/quiz_builder.html', lesson=lesson, quiz=quiz, existing_questions=existing_questions)

@admin_bp.route('/quizzes')
def all_quizzes():
    # Group quizzes by course
    courses = Course.query.all()
    # Filter courses that have quizzes
    courses_with_quizzes = []
    for course in courses:
        quizzes = []
        for module in course.modules:
            for lesson in module.lessons:
                if lesson.quiz:
                    quizzes.append(lesson.quiz)
        if quizzes:
            courses_with_quizzes.append({'course': course, 'quizzes': quizzes})
            
    return render_template('admin/quizzes.html', courses_with_quizzes=courses_with_quizzes)

@admin_bp.route('/lesson/<int:lesson_id>/quiz/delete', methods=['POST'])
@login_required
def delete_quiz(lesson_id):
    if current_user.role != 'admin':
        abort(403)
    
    # Get lesson first to redirect back correctly
    lesson = Lesson.query.get_or_404(lesson_id)
    course_id = lesson.module.course.id
    
    # Delete ALL quizzes associated with this lesson to clean up any duplicates
    quizzes = Quiz.query.filter_by(lesson_id=lesson_id).all()
    for q in quizzes:
        db.session.delete(q)
        
    db.session.commit()
    flash('Quiz(zes) deleted successfully.', 'success')
    return redirect(url_for('admin_bp.course_content', course_id=course_id))

@admin_bp.route('/lesson/<int:lesson_id>/delete', methods=['POST'])
@login_required
def delete_lesson(lesson_id):
    if current_user.role != 'admin':
        abort(403)
        
    lesson = Lesson.query.get_or_404(lesson_id)
    course_id = lesson.module.course.id
    db.session.delete(lesson)
    db.session.commit()
    flash('Lesson deleted successfully.', 'success')
    return redirect(url_for('admin_bp.course_content', course_id=course_id))

@admin_bp.route('/course/<int:course_id>/quick_add', methods=['POST'])
@login_required
def quick_add_content(course_id):
    if current_user.role != 'admin':
        abort(403)
        
    course = Course.query.get_or_404(course_id)
    module_id = request.form.get('module_id')
    title = request.form.get('title')
    content_type = request.form.get('type') # 'quiz' or 'assignment'
    
    if module_id and title:
        count = Lesson.query.filter_by(module_id=module_id).count()
        lesson = Lesson(
            title=title, 
            module_id=module_id, 
            order_index=count
            # No video_url implied
        )
        db.session.add(lesson)
        db.session.commit()
        
        if content_type == 'quiz':
            return redirect(url_for('admin_bp.add_quiz', lesson_id=lesson.id))
        elif content_type == 'assignment':
             # For assignment, we don't have a dedicated page, so we use the modal logic.
             # We can redirect to course content and trigger modal, OR just create a shell assignment.
             # Let's create a shell assignment to make it visible
            assignment = Assignment(lesson_id=lesson.id, instructions="Pending setup...", max_score=100)
            db.session.add(assignment)
            db.session.commit()
            
            flash(f'New {content_type} created. Please edit details.', 'success')
            return redirect(url_for('admin_bp.course_content', course_id=course.id))
            
    flash('Failed to create content.', 'danger')
    return redirect(url_for('admin_bp.course_content', course_id=course.id))

@admin_bp.route('/lesson/<int:lesson_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_lesson(lesson_id):
    if current_user.role != 'admin':
        abort(403)
        
    lesson = Lesson.query.get_or_404(lesson_id)
    
    if request.method == 'POST':
        lesson.title = request.form.get('title')
        lesson.video_url = request.form.get('video_url')
        db.session.commit()
        flash('Lesson updated successfully.', 'success')
        return redirect(url_for('admin_bp.course_content', course_id=lesson.module.course.id))
        
    return render_template('admin/edit_lesson.html', lesson=lesson)

# --- Assignments ---
from app.models import Assignment, Submission
from app.routes import allowed_file
from werkzeug.utils import secure_filename
import os
from flask import send_file, current_app

@admin_bp.route('/assignments')
@login_required
def all_assignments():
    courses = Course.query.all()
    courses_with_assignments = []
    
    for course in courses:
        assignments = []
        for module in course.modules:
            for lesson in module.lessons:
                if lesson.assignment:
                    assignments.append(lesson.assignment)
        if assignments:
            courses_with_assignments.append({'course': course, 'assignments': assignments})
            
    return render_template('admin/assignments.html', courses_with_assignments=courses_with_assignments)

@admin_bp.route('/lesson/<int:lesson_id>/add_assignment', methods=['POST'])
@login_required
def add_assignment(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    instructions = request.form.get('instructions')
    max_score = request.form.get('max_score')
    
    if instructions:
        assignment = Assignment(lesson_id=lesson_id, instructions=instructions, max_score=int(max_score) if max_score else 100)
        
        # Handle Resource Upload
        if 'resource_file' in request.files:
            file = request.files['resource_file']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"resource_{lesson.id}_{file.filename}")
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                assignment.resource_path = filename
                
        db.session.add(assignment)
        db.session.commit()
        flash('Assignment added successfully!', 'success')
    else:
        flash('Instructions are required.', 'danger')
        
    return redirect(url_for('admin_bp.course_content', course_id=lesson.module.course.id))

@admin_bp.route('/assignment/<int:assignment_id>/edit', methods=['POST'])
@login_required
def edit_assignment(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    assignment.instructions = request.form.get('instructions')
    assignment.max_score = int(request.form.get('max_score'))
    
    # Handle Resource Upload
    print(f"DEBUG: Processing assignment edit for ID {assignment_id}")
    if 'resource_file' in request.files:
        file = request.files['resource_file']
        print(f"DEBUG: File found in request: {file.filename}")
        if file and file.filename != '' and allowed_file(file.filename):
            # Delete old file if exists? (Optional, good practice)
            filename = secure_filename(f"resource_{assignment.lesson_id}_{file.filename}")
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            assignment.resource_path = filename
            print(f"DEBUG: File saved to {file_path}, resource_path set to {filename}")
        else:
            print(f"DEBUG: File validation failed. Filename: {file.filename}")
            if file.filename != '':
                flash('Invalid file type. Allowed: pdf, doc, zip, txt, images', 'warning')
    else:
        print("DEBUG: No 'resource_file' in request.files")
            
    db.session.commit()
    print(f"DEBUG: Committed. Assignment resource_path is now: {assignment.resource_path}")
    flash('Assignment updated.', 'success')
    return redirect(url_for('admin_bp.course_content', course_id=assignment.lesson.module.course.id))

@admin_bp.route('/assignment/<int:assignment_id>/delete', methods=['POST'])
@login_required
def delete_assignment(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    course_id = assignment.lesson.module.course.id
    db.session.delete(assignment)
    db.session.commit()
    flash('Assignment removed.', 'success')
    return redirect(url_for('admin_bp.course_content', course_id=course_id))

@admin_bp.route('/assignment/<int:assignment_id>/submissions')
@login_required
def assignment_submissions(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    return render_template('admin/assignment_submissions.html', assignment=assignment)

@admin_bp.route('/submission/<int:submission_id>/grade', methods=['POST'])
@login_required
def grade_submission(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    grade = request.form.get('grade')
    feedback = request.form.get('feedback')
    
    if grade:
        submission.grade = int(grade)
        submission.feedback = feedback
        db.session.commit()
        flash('Grade updated successfully.', 'success')
    
    return redirect(url_for('admin_bp.assignment_submissions', assignment_id=submission.assignment.id))


@admin_bp.route('/student/<int:user_id>/change_password', methods=['POST'])
@login_required
def change_student_password(user_id):
    if current_user.role != 'admin':
        flash('Access Denied', 'danger')
        return redirect(url_for('main.index'))
        
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password')
    
    if not new_password:
        flash('Password cannot be empty', 'danger')
        return redirect(url_for('admin_bp.students'))
        
    hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
    user.password_hash = hashed_password
    user.plain_password = new_password # Saving plain password as requested by admin
    db.session.commit()
    
    flash(f'Password updated for {user.full_name}', 'success')
    return redirect(url_for('admin_bp.students'))

@admin_bp.route('/student/reveal_password', methods=['POST'])
@login_required
def reveal_student_password():
    if current_user.role != 'admin':
        return {'error': 'Unauthorized'}, 403
        
    data = request.get_json()
    student_id = data.get('student_id')
    admin_password = data.get('admin_password')
    
    if not student_id or not admin_password:
        return {'error': 'Missing data'}, 400
        
    # Verify admin password
    if not bcrypt.check_password_hash(current_user.password_hash, admin_password):
        return {'error': 'Incorrect Admin Password'}, 401
        
    student = User.query.get(student_id)
    if not student:
        return {'error': 'Student not found'}, 404
        
    return {'plain_password': student.plain_password if student.plain_password else None}

@admin_bp.route('/student/<int:user_id>/toggle_status', methods=['POST'])
@login_required
def toggle_student_status(user_id):
    if current_user.role != 'admin':
        return {'success': False, 'message': 'Unauthorized'}, 403
        
    user = User.query.get_or_404(user_id)
    
    if user.status == 'approved':
        user.status = 'disabled'
        message = 'Account disabled'
    elif user.status == 'disabled':
        user.status = 'approved'
        message = 'Account activated'
    else:
        # If pending or rejected, perhaps just approve it? 
        # For now, let's treat non-approved as disabled -> approve
        user.status = 'approved'
        message = 'Account activated'
        
    db.session.commit()
    return {'success': True, 'status': user.status, 'message': message}
