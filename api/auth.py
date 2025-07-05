"""
Authentication module for LexAI Practice Partner
Provides secure user registration, login, and session management
"""

import bcrypt
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import session, request, jsonify, redirect, url_for, flash
from database import db, User
import logging

logger = logging.getLogger(__name__)

class AuthManager:
    """Centralized authentication management"""
    
    @staticmethod
    def generate_salt():
        """Generate secure salt for password hashing"""
        return bcrypt.gensalt()
    
    @staticmethod
    def hash_password(password, salt=None):
        """Hash password with bcrypt"""
        if salt is None:
            salt = AuthManager.generate_salt()
        return bcrypt.hashpw(password.encode('utf-8'), salt)
    
    @staticmethod
    def verify_password(password, hashed_password):
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password)
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    @staticmethod
    def generate_session_token():
        """Generate secure session token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def validate_email(email):
        """Basic email validation"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_password_strength(password):
        """Validate password meets security requirements"""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"
        
        return True, "Password is valid"

def login_required(f):
    """Decorator to require authentication for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        
        # Check if user still exists and is active
        user = User.query.get(session['user_id'])
        if not user or not user.is_active:
            session.clear()
            if request.is_json:
                return jsonify({'error': 'Invalid session'}), 401
            return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_active or user.role != 'admin':
            if request.is_json:
                return jsonify({'error': 'Admin access required'}), 403
            flash('Admin access required', 'error')
            return redirect(url_for('dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Get the current authenticated user"""
    if 'user_id' not in session:
        return None
    
    return User.query.get(session['user_id'])

def create_user_session(user):
    """Create a new user session"""
    session['user_id'] = user.id
    session['user_email'] = user.email
    session['user_role'] = user.role
    session['session_token'] = AuthManager.generate_session_token()
    session['login_time'] = datetime.utcnow().isoformat()
    
    # Update user's last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    logger.info(f"User session created: {user.email}")

def destroy_user_session():
    """Destroy current user session"""
    if 'user_email' in session:
        logger.info(f"User session destroyed: {session['user_email']}")
    session.clear()

def register_user(email, password, first_name, last_name, firm_name=None):
    """Register a new user"""
    try:
        # Validate input
        if not AuthManager.validate_email(email):
            return False, "Invalid email format"
        
        is_valid, password_msg = AuthManager.validate_password_strength(password)
        if not is_valid:
            return False, password_msg
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email.lower()).first()
        if existing_user:
            return False, "Email already registered"
        
        # Create new user
        hashed_password = AuthManager.hash_password(password)
        
        new_user = User(
            email=email.lower(),
            password_hash=hashed_password,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            firm_name=firm_name.strip() if firm_name else None,
            role='user',
            is_active=True,
            created_at=datetime.utcnow()
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        logger.info(f"New user registered: {email}")
        return True, "Registration successful"
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Registration error: {e}")
        return False, "Registration failed. Please try again."

def authenticate_user(email, password):
    """Authenticate user login"""
    try:
        user = User.query.filter_by(email=email.lower()).first()
        
        if not user:
            return None, "Invalid email or password"
        
        if not user.is_active:
            return None, "Account is disabled"
        
        if not AuthManager.verify_password(password, user.password_hash):
            return None, "Invalid email or password"
        
        return user, "Login successful"
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None, "Authentication failed"

def update_user_password(user_id, current_password, new_password):
    """Update user password"""
    try:
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"
        
        # Verify current password
        if not AuthManager.verify_password(current_password, user.password_hash):
            return False, "Current password is incorrect"
        
        # Validate new password
        is_valid, password_msg = AuthManager.validate_password_strength(new_password)
        if not is_valid:
            return False, password_msg
        
        # Update password
        user.password_hash = AuthManager.hash_password(new_password)
        user.password_updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Password updated for user: {user.email}")
        return True, "Password updated successfully"
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Password update error: {e}")
        return False, "Password update failed"

def reset_user_password(email):
    """Initiate password reset process"""
    try:
        user = User.query.filter_by(email=email.lower()).first()
        if not user:
            # Don't reveal if email exists for security
            return True, "If this email is registered, you will receive reset instructions"
        
        # Generate reset token
        reset_token = AuthManager.generate_session_token()
        user.reset_token = reset_token
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        db.session.commit()
        
        # TODO: Send email with reset link
        logger.info(f"Password reset requested for: {email}")
        return True, "Reset instructions sent to email"
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Password reset error: {e}")
        return False, "Password reset failed"

def verify_reset_token(token):
    """Verify password reset token"""
    try:
        user = User.query.filter_by(reset_token=token).first()
        
        if not user:
            return None, "Invalid reset token"
        
        if datetime.utcnow() > user.reset_token_expires:
            return None, "Reset token has expired"
        
        return user, "Token is valid"
        
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None, "Token verification failed"

def complete_password_reset(token, new_password):
    """Complete password reset with new password"""
    try:
        user, message = verify_reset_token(token)
        if not user:
            return False, message
        
        # Validate new password
        is_valid, password_msg = AuthManager.validate_password_strength(new_password)
        if not is_valid:
            return False, password_msg
        
        # Update password and clear reset token
        user.password_hash = AuthManager.hash_password(new_password)
        user.password_updated_at = datetime.utcnow()
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()
        
        logger.info(f"Password reset completed for: {user.email}")
        return True, "Password reset successfully"
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Password reset completion error: {e}")
        return False, "Password reset failed"