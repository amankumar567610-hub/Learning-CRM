from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

main = Blueprint('main', __name__)

from app.models import Lesson, Course
from app import db, bcrypt
from flask import current_app
from werkzeug.utils import secure_filename
import os
import json

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('main.dashboard'))
    
    # Calculate progress for each enrolled course
    enrolled_courses_data = []
    from app.models import LessonProgress, Submission
    
    total_enrolled = len(current_user.enrolled_courses)
    total_progress_sum = 0
    pending_assignments_count = 0
    
    for course in current_user.enrolled_courses:
        total_lessons = 0
        for module in course.modules:
            total_lessons += len(module.lessons)
            
            # Check for pending assignments in this course
            for lesson in module.lessons:
                if lesson.assignment:
                    submission = Submission.query.filter_by(
                        user_id=current_user.id,
                        assignment_id=lesson.assignment.id
                    ).first()
                    if not submission:
                        pending_assignments_count += 1
            
        completed_lessons = 0
        all_lessons_ids = [l.id for m in course.modules for l in m.lessons]
        
        if all_lessons_ids:
            completed_lessons = LessonProgress.query.filter(
                LessonProgress.user_id == current_user.id,
                LessonProgress.lesson_id.in_(all_lessons_ids),
                LessonProgress.is_completed == True
            ).count()
            
        progress_percent = int((completed_lessons / total_lessons * 100)) if total_lessons > 0 else 0
        total_progress_sum += progress_percent
        
        enrolled_courses_data.append({
            'course': course,
            'progress': progress_percent,
            'total_lessons': total_lessons,
            'completed': completed_lessons
        })
        
    avg_progress = int(total_progress_sum / total_enrolled) if total_enrolled > 0 else 0
        
    return render_template('student_dashboard.html', 
                           courses_data=enrolled_courses_data,
                           total_enrolled=total_enrolled,
                           avg_progress=avg_progress,
                           pending_assignments_count=pending_assignments_count)

@main.route('/student/profile/update', methods=['POST'])
@login_required
def update_profile():
    if current_user.role != 'student':
        abort(403)
        
    # 1. Handle Profile Image
    if 'profile_image' in request.files:
        file = request.files['profile_image']
        if file and file.filename != '' and allowed_file(file.filename):
            try:
                # Cloudinary Upload
                from app.utils import upload_file
                image_url = upload_file(file, folder="avatars")
                
                if image_url:
                    current_user.profile_image = image_url
                    flash('Profile image updated!', 'success')
                else:
                     # Fallback to local (or error if keys missing in prod)
                    filename = secure_filename(f"avatar_{current_user.id}_{file.filename}")
                    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    current_user.profile_image = filename # Store filename for local fallback
                    flash('Profile image updated (Local)!', 'success')

            except Exception as e:
                print(f"Error saving avatar: {e}")
                flash('Error uploading image.', 'danger')
    
    # 2. Handle Password Change
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if current_password and new_password:
        if not bcrypt.check_password_hash(current_user.password_hash, current_password):
            flash('Current password incorrect.', 'danger')
        elif new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
        else:
            hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
            current_user.password_hash = hashed_password
            current_user.plain_password = new_password # Update reference
            flash('Password changed successfully!', 'success')
            
    db.session.commit()
    return redirect(url_for('main.student_dashboard'))

@main.route('/course/<int:course_id>')
@login_required
def course_view(course_id):
    course = Course.query.get_or_404(course_id)
    # Security check: Ensure user is enrolled
    if current_user.role != 'admin' and course not in current_user.enrolled_courses:
        flash('You are not enrolled in this course.', 'danger')
        return redirect(url_for('main.student_dashboard'))
    
    # Get completed lessons for this user
    from app.models import LessonProgress, QuizResult, Quiz
    completed_progress = LessonProgress.query.filter_by(user_id=current_user.id, is_completed=True).all()
    completed_lesson_ids = [p.lesson_id for p in completed_progress]
    
    # Check if quizzes are attempted
    # Create a dictionary of quiz_id -> latest_result
    quiz_results = {}
    from app.models import QuizResult
    results = QuizResult.query.filter_by(user_id=current_user.id).all()
    for r in results:
        # We want the latest one, so we can check if we already have one or use logic to keep latest
        # Since we might have duplicates if we allowed re-takes, careful.
        # But for the UI "Take Quiz" vs "View Score", we just need to know if ANY exists (or latest).
        if r.quiz_id not in quiz_results:
             quiz_results[r.quiz_id] = r
        else:
            # Overwrite if newer (assuming results are ordered or we compare dates)
            if r.attempted_at > quiz_results[r.quiz_id].attempted_at:
                quiz_results[r.quiz_id] = r
                
    # Fetch Assignment Submissions
    # Create dict assignment_id -> submission
    assignment_submissions = {}
    from app.models import Submission
    if current_user.role == 'student':
        subs = Submission.query.filter_by(user_id=current_user.id).all()
        for s in subs:
            assignment_submissions[s.assignment_id] = s

    # Determine if it's a student view (for template logic)
    student_view = (current_user.role == 'student')
    
    return render_template('admin/course_content.html', course=course, modules=course.modules, student_view=student_view, completed_lesson_ids=completed_lesson_ids, quiz_results=quiz_results, submissions=assignment_submissions)

@main.route('/quiz/<int:result_id>/result')
@login_required
def view_quiz_result(result_id):
    from app.models import QuizResult, Quiz, Lesson
    import json
    
    result = QuizResult.query.get_or_404(result_id)
    if result.user_id != current_user.id:
        abort(403)
        
    quiz = Quiz.query.get(result.quiz_id)
    lesson = quiz.lesson
    
    # Prepare questions data for Answer Key
    questions_data = []
    
    # Parse stored answers
    stored_answers = {}
    if result.answers:
        try:
            stored_answers = json.loads(result.answers)
        except:
            stored_answers = {}

    for q in quiz.questions:
        # stored_answers keys are strings of question IDs
        user_choice = stored_answers.get(str(q.id))
        
        questions_data.append({
            'text': q.question_text,
            'options': json.loads(q.options),
            'correct_option': q.correct_option,
            'user_answer': user_choice
        })
        
    return render_template('quiz_result.html', result=result, quiz=quiz, lesson=lesson, questions_data=questions_data)

@main.route('/admin/dashboard')
@login_required
def dashboard():
    from app.models import User, Course, Quiz, Notification
    
    # Stats
    total_students = User.query.filter_by(role='student').count()
    pending_requests = User.query.filter_by(role='student', status='pending').count()
    active_students = User.query.filter_by(role='student', status='approved').count()
    total_courses = Course.query.count()
    
    # Notifications
    notifications = Notification.query.filter_by(is_read=False).order_by(Notification.created_at.desc()).all()
    

    return render_template('admin/dashboard.html', 
                           user=current_user,
                           total_students=total_students,
                           pending_requests=pending_requests,
                           active_students=active_students,
                           total_courses=total_courses,
                           notifications=notifications)

@main.route('/admin/notification/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    from app.models import Notification
    if current_user.role != 'admin':
        return {'success': False}, 403
        
    notification = Notification.query.get_or_404(notification_id)
    notification.is_read = True
    db.session.commit()
    return {'success': True}

@main.route('/lesson/<int:lesson_id>')
@login_required
def lesson_player(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    
    # Check if completed
    from app.models import LessonProgress, Module, Quiz
    progress = LessonProgress.query.filter_by(user_id=current_user.id, lesson_id=lesson.id).first()
    is_completed = progress.is_completed if progress else False
    
    # Check if quiz exists
    quiz = Quiz.query.filter_by(lesson_id=lesson.id).first()
    quiz_result = None
    if quiz:
        from app.models import QuizResult
        # ordering by desc to get latest attempt
        quiz_result = QuizResult.query.filter_by(user_id=current_user.id, quiz_id=quiz.id).order_by(QuizResult.attempted_at.desc()).first()
    
    # Check if assignment exists
    from app.models import Assignment, Submission
    assignment = Assignment.query.filter_by(lesson_id=lesson.id).first()
    submission = None
    if assignment:
        submission = Submission.query.filter_by(user_id=current_user.id, assignment_id=assignment.id).first()
    
    # Find next lesson logic
    next_lesson = None
    # 1. Try next lesson in same module
    next_in_module = Lesson.query.filter_by(module_id=lesson.module_id).filter(Lesson.order_index > lesson.order_index).order_by(Lesson.order_index).first()
    if next_in_module:
        next_lesson = next_in_module
    else:
        # 2. Try first lesson of next module
        current_module = Module.query.get(lesson.module_id)
        next_module = Module.query.filter_by(course_id=current_module.course_id).filter(Module.order_index > current_module.order_index).order_by(Module.order_index).first()
        if next_module:
            next_lesson = Lesson.query.filter_by(module_id=next_module.id).order_by(Lesson.order_index).first()
    
    return render_template('lesson_player.html', lesson=lesson, is_completed=is_completed, next_lesson=next_lesson, quiz=quiz, assignment=assignment, submission=submission, quiz_result=quiz_result)

@main.route('/lesson/<int:lesson_id>/complete', methods=['POST'])
@login_required
def mark_complete(lesson_id):
    from app import db
    from app.models import LessonProgress
    from datetime import datetime
    
    lesson = Lesson.query.get_or_404(lesson_id)
    
    # Check existing progress
    progress = LessonProgress.query.filter_by(user_id=current_user.id, lesson_id=lesson.id).first()
    
    if not progress:
        progress = LessonProgress(user_id=current_user.id, lesson_id=lesson.id, is_completed=True, completed_at=datetime.utcnow())
        db.session.add(progress)
    else:
        progress.is_completed = not progress.is_completed # Toggle
        progress.completed_at = datetime.utcnow() if progress.is_completed else None
        
    db.session.commit()
    
    flash('Lesson status updated.', 'success')
    return redirect(url_for('main.lesson_player', lesson_id=lesson.id))

@main.route('/admin/submission/<int:submission_id>/reject', methods=['POST'])
@login_required
def reject_assignment(submission_id):
    from app import db
    from app.models import Submission
    from flask import request
    
    if current_user.role != 'admin':
        abort(403)
        
    submission = Submission.query.get_or_404(submission_id)
    lesson_id = submission.assignment.lesson_id
    
    # Delete the submission file from the server
    if submission.file_path:
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], submission.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
            
    # Delete the submission record from the database
    db.session.delete(submission)
    db.session.commit()
    
    flash('Assignment rejected. Student can now resubmit.', 'warning')
    
    # Check if a 'next' URL is provided (e.g., from Admin Panel)
    next_url = request.form.get('next') or request.args.get('next')
    if next_url:
        return redirect(next_url)
        
    return redirect(url_for('main.lesson_player', lesson_id=lesson_id))

# --- Student Quiz ---
from app.models import Quiz, Question, QuizResult
import json

@main.route('/student/assignments')
@login_required
def student_assignments():
    if current_user.role != 'student':
        return redirect(url_for('main.index'))
        
    assignments_data = []
    
    # Iterate through enrolled courses to find all assignments
    for course in current_user.enrolled_courses:
        for module in course.modules:
            for lesson in module.lessons:
                if lesson.assignment:
                    submission = Submission.query.filter_by(user_id=current_user.id, assignment_id=lesson.assignment.id).first()
                    assignments_data.append({
                        'course': course,
                        'lesson': lesson,
                        'assignment': lesson.assignment,
                        'submission': submission,
                        'status': 'Graded' if submission and submission.grade is not None else ('Submitted' if submission else 'Pending')
                    })
    
    # Sort by status (Pending first)
    assignments_data.sort(key=lambda x: 0 if x['status'] == 'Pending' else 1)
                    
    return render_template('student_assignments.html', assignments=assignments_data)

@main.route('/lesson/<int:lesson_id>/quiz')
@login_required
def take_quiz(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    quiz = Quiz.query.filter_by(lesson_id=lesson_id).first()
    
    if not quiz:
        flash('No quiz available for this lesson.', 'warning')
        return redirect(url_for('main.lesson_player', lesson_id=lesson_id))
    
    # Parse options for template
    questions_data = []
    for q in quiz.questions:
        questions_data.append({
            'id': q.id,
            'text': q.question_text,
            'options': json.loads(q.options)
        })
        
    return render_template('quiz_taker.html', lesson=lesson, quiz=quiz, questions=questions_data)

@main.route('/lesson/<int:lesson_id>/quiz/submit', methods=['POST'])
@login_required
def submit_quiz(lesson_id):
    from app import db
    lesson = Lesson.query.get_or_404(lesson_id)
    quiz = Quiz.query.filter_by(lesson_id=lesson_id).first_or_404()
    
    score = 0
    total_questions = len(quiz.questions)
    
    for q in quiz.questions:
        selected_option = request.form.get(f'question_{q.id}')
        if selected_option and int(selected_option) == q.correct_option:
            score += 1
            
    # Calculate percentage
    percentage = int((score / total_questions) * 100) if total_questions > 0 else 0
    passed = percentage >= 70 # Pass mark
    
    # Store answers as JSON {question_id: selected_option_int}
    answers_dict = {}
    for q in quiz.questions:
        selected = request.form.get(f'question_{q.id}')
        if selected:
            answers_dict[str(q.id)] = int(selected)
            
    # Save result
    result = QuizResult(user_id=current_user.id, quiz_id=quiz.id, score=percentage, passed=passed, answers=json.dumps(answers_dict))
    db.session.add(result)
    db.session.commit()
    
    # Prepare questions data for Answer Key
    questions_data = []
    for q in quiz.questions:
        user_choice = answers_dict.get(str(q.id))
        questions_data.append({
            'text': q.question_text,
            'options': json.loads(q.options),
            'correct_option': q.correct_option,
            'user_answer': user_choice
        })
    
    return render_template('quiz_result.html', result=result, quiz=quiz, lesson=lesson, questions_data=questions_data)

@main.route('/student/quizzes')
@login_required
def student_quizzes():
    if current_user.role != 'student':
        return redirect(url_for('main.index'))
        
    enrolled_quizzes = []
    for course in current_user.enrolled_courses:
        for module in course.modules:
            for lesson in module.lessons:
                if lesson.quiz:
                    # Check if attempted
                    result = QuizResult.query.filter_by(user_id=current_user.id, quiz_id=lesson.quiz.id).order_by(QuizResult.attempted_at.desc()).first()
                    enrolled_quizzes.append({
                        'quiz': lesson.quiz,
                        'course': course,
                        'result': result
                    })
                    
    return render_template('student_quizzes.html', quizzes=enrolled_quizzes)

# --- Assignments ---
from app.models import Assignment, Submission
from werkzeug.utils import secure_filename
import os
from flask import send_file, current_app, abort

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'zip', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main.route('/lesson/<int:lesson_id>/assignment/upload', methods=['POST'])
@login_required
def upload_assignment(lesson_id):
    print(f"DEBUG: Upload started for lesson {lesson_id}")
    lesson = Lesson.query.get_or_404(lesson_id)
    assignment = Assignment.query.filter_by(lesson_id=lesson_id).first_or_404()
    
    if 'file' not in request.files:
        print("DEBUG: No 'file' key in request.files")
        flash('No file part', 'danger')
        return redirect(url_for('main.lesson_player', lesson_id=lesson_id))
        
    file = request.files['file']
    print(f"DEBUG: File uploaded: {file.filename}")
    
    if file.filename == '':
        print("DEBUG: Filename is empty")
        flash('No selected file', 'danger')
        return redirect(url_for('main.lesson_player', lesson_id=lesson_id))
        
    if file and allowed_file(file.filename):
        # Cloudinary Upload
        from app.utils import upload_file
        file_url = upload_file(file, folder="assignments")
        
        filename = secure_filename(f"{current_user.id}_{assignment.id}_{file.filename}") # Keep for local fallback name
        
        if file_url:
             # Store URL
             stored_path = file_url
             print(f"DEBUG: Uploaded to Cloudinary: {stored_path}")
        else:
             # Fallback Local
             file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
             try:
                file.save(file_path)
                stored_path = filename
                print(f"DEBUG: Saved locally to {file_path}")
             except Exception as e:
                print(f"DEBUG: File save error: {e}")
                flash('Error saving file.', 'danger')
                return redirect(url_for('main.lesson_player', lesson_id=lesson_id))
        
        # Check if updating existing submission
        submission = Submission.query.filter_by(user_id=current_user.id, assignment_id=assignment.id).first()
        
        if submission:
            # Prevent resubmission if graded
            if submission.grade is not None:
                 print("DEBUG: Attempt to resubmit graded assignment blocked")
                 flash('Cannot resubmit. Assignment has already been graded.', 'warning')
                 return redirect(url_for('main.lesson_player', lesson_id=lesson_id))

            submission.file_path = stored_path 
            from datetime import datetime
            submission.submitted_at = datetime.utcnow()
            print("DEBUG: Updated existing submission")
        else:
            submission = Submission(
                user_id=current_user.id,
                assignment_id=assignment.id,
                file_path=stored_path
            )
            db.session.add(submission)
            print("DEBUG: Created new submission")

        # Create Admin Notification
        from app.models import Notification
        course_title = lesson.module.course.title
        msg = f"Submission in {course_title}: {lesson.title} by {current_user.full_name}"
        notification = Notification(
            message=msg,
            link=url_for('admin_bp.assignment_submissions', assignment_id=assignment.id)
        )
        db.session.add(notification)
            
        db.session.commit()
        flash('Assignment submitted successfully!', 'success')
        
    else:
        print(f"DEBUG: Invalid file type: {file.filename}")
        flash('Invalid file type. Allowed: pdf, doc, zip, images', 'danger')
        
    return redirect(url_for('main.lesson_player', lesson_id=lesson_id))

@main.route('/submission/<int:submission_id>/download')
@login_required
def download_submission(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    
    # Security check: Only Admin or the student who owns it can download
    if current_user.role != 'admin' and current_user.id != submission.user_id:
        abort(403)
        
    file_path_or_url = submission.file_path
    
    # Check if it's a Cloudinary URL
    if file_path_or_url and file_path_or_url.startswith('http'):
        return redirect(file_path_or_url)

    # Fallback to local
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], submission.file_path)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        flash('File not found.', 'danger')
        return redirect(url_for('main.index'))

@main.route('/assignment/<int:assignment_id>/resource')
@login_required
def download_assignment_resource(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # Check enrollment/access rights
    allow_download = False
    if current_user.role == 'admin':
        allow_download = True
    elif assignment.lesson.module.course in current_user.enrolled_courses:
        allow_download = True
        
    if not allow_download:
        abort(403)

    if not assignment.resource_path:
        abort(404)
        
    file_path_or_url = assignment.resource_path
    if file_path_or_url and file_path_or_url.startswith('http'):
        return redirect(file_path_or_url)
        
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], assignment.resource_path)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        flash('Resource file not found.', 'danger')
        return redirect(request.referrer or url_for('main.index'))
