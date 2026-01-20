from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db, bcrypt
from app.models import User

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('main.dashboard'))
        return redirect(url_for('main.student_dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and bcrypt.check_password_hash(user.password_hash, password):
            if user.role != 'admin':
                # For students, check approval status
                if user.status == 'disabled':
                    flash('Your account has been disabled. Please contact the administrator.', 'danger')
                    return redirect(url_for('auth.login'))
                if user.status != 'approved':
                    flash('Account pending approval. Please wait for admin verification.', 'warning')
                    return redirect(url_for('auth.login'))
            
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('main.dashboard'))
            else:
                return redirect(url_for('main.student_dashboard')) # Student Dashboard
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
            
    return render_template('auth/login.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('auth.register'))
            
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(
            full_name=full_name,
            email=email, 
            phone_number=request.form.get('phone_number'),
            password_hash=hashed_password, 
            plain_password=password, # Save plain password for admin reference
            role='student', 
            status='pending'
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Account created! Please wait for admin approval.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html')


@auth.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
