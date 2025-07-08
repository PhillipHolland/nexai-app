"""
LexAI Practice Partner - Database Configuration and Utilities
Production-ready database setup with Neon PostgreSQL and Redis
"""

import os
import redis
from flask import current_app
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from models import db, User, Client, Case, Task, Document, TimeEntry, Invoice, Expense, CalendarEvent, Tag, AuditLog, Session
from werkzeug.security import generate_password_hash
import logging
from datetime import datetime, timedelta, timezone
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database management utilities"""
    
    def __init__(self, app=None):
        self.app = app
        self.redis_client = None
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize database with Flask app"""
        self.app = app
        self.setup_database_config()
        self.setup_redis()
        
        # Initialize SQLAlchemy
        db.init_app(app)
        
        # Create tables if they don't exist
        with app.app_context():
            self.create_tables()
    
    def setup_database_config(self):
        """Configure database connection"""
        # Get database URL from environment (Neon PostgreSQL)
        database_url = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL')
        
        if not database_url:
            # Fallback to local SQLite for development
            database_url = 'sqlite:///lexai_platform.db'
            logger.warning("No PostgreSQL URL found, using SQLite fallback")
        else:
            # Ensure proper SSL configuration for Neon
            if 'sslmode' not in database_url:
                database_url += '?sslmode=require'
            logger.info("Using PostgreSQL database")
        
        # Configure SQLAlchemy
        self.app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        self.app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'connect_args': {
                'connect_timeout': 10,
                'application_name': 'lexai_practice_partner'
            }
        }
        
        # Disable modification tracking for performance
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    def setup_redis(self):
        """Configure Redis connection"""
        try:
            redis_url = os.getenv('REDIS_URL') or os.getenv('KV_URL')
            
            if redis_url:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                # Test connection
                self.redis_client.ping()
                logger.info("Redis connected successfully")
            else:
                logger.warning("No Redis URL found, session persistence disabled")
                self.redis_client = None
                
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self.redis_client = None
    
    def create_tables(self):
        """Create all database tables"""
        try:
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Create initial data if needed
            self.create_initial_data()
            
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    def create_initial_data(self):
        """Create initial data (admin user, default tags, etc.)"""
        try:
            # Check if admin user exists
            admin_user = User.query.filter_by(email='admin@lexai.com').first()
            
            if not admin_user:
                # Create admin user
                from models import UserRole
                admin_user = User(
                    email='admin@lexai.com',
                    first_name='System',
                    last_name='Administrator',
                    role=UserRole.ADMIN,
                    firm_name='LexAI Practice Partner',
                    is_active=True,
                    email_verified=True
                )
                admin_user.set_password('admin123')  # Change in production!
                
                db.session.add(admin_user)
                logger.info("Created admin user")
            
            # Create default tags
            default_tags = [
                {'name': 'urgent', 'color': '#ef4444', 'description': 'Urgent priority items'},
                {'name': 'litigation', 'color': '#dc2626', 'description': 'Litigation matters'},
                {'name': 'contract', 'color': '#2563eb', 'description': 'Contract-related items'},
                {'name': 'corporate', 'color': '#059669', 'description': 'Corporate law matters'},
                {'name': 'confidential', 'color': '#7c3aed', 'description': 'Confidential documents'},
                {'name': 'discovery', 'color': '#f59e0b', 'description': 'Discovery phase items'},
                {'name': 'court', 'color': '#dc2626', 'description': 'Court-related activities'},
                {'name': 'client-meeting', 'color': '#10b981', 'description': 'Client meetings'}
            ]
            
            for tag_data in default_tags:
                existing_tag = Tag.query.filter_by(name=tag_data['name']).first()
                if not existing_tag:
                    tag = Tag(**tag_data)
                    db.session.add(tag)
            
            db.session.commit()
            logger.info("Initial data created successfully")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating initial data: {e}")
    
    def health_check(self):
        """Check database health"""
        try:
            # Test database connection
            db.session.execute(text('SELECT 1'))
            db_status = 'healthy'
        except Exception as e:
            db_status = f'error: {str(e)}'
        
        # Test Redis connection
        redis_status = 'not_configured'
        if self.redis_client:
            try:
                self.redis_client.ping()
                redis_status = 'healthy'
            except Exception as e:
                redis_status = f'error: {str(e)}'
        
        return {
            'database': db_status,
            'redis': redis_status,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

class RedisSessionManager:
    """Redis-based session management"""
    
    def __init__(self, redis_client, prefix='lexai_session:'):
        self.redis_client = redis_client
        self.prefix = prefix
        self.default_ttl = 86400  # 24 hours
    
    def create_session(self, user_id, session_data, ttl=None):
        """Create a new session"""
        if not self.redis_client:
            return None
        
        session_id = f"sess_{user_id}_{datetime.now().timestamp()}"
        session_key = f"{self.prefix}{session_id}"
        
        session_data.update({
            'user_id': user_id,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'last_activity': datetime.now(timezone.utc).isoformat()
        })
        
        try:
            self.redis_client.setex(
                session_key,
                ttl or self.default_ttl,
                json.dumps(session_data)
            )
            return session_id
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return None
    
    def get_session(self, session_id):
        """Get session data"""
        if not self.redis_client or not session_id:
            return None
        
        session_key = f"{self.prefix}{session_id}"
        
        try:
            session_data = self.redis_client.get(session_key)
            if session_data:
                return json.loads(session_data)
        except Exception as e:
            logger.error(f"Error getting session: {e}")
        
        return None
    
    def update_session(self, session_id, session_data, ttl=None):
        """Update session data"""
        if not self.redis_client or not session_id:
            return False
        
        session_key = f"{self.prefix}{session_id}"
        session_data['last_activity'] = datetime.now(timezone.utc).isoformat()
        
        try:
            self.redis_client.setex(
                session_key,
                ttl or self.default_ttl,
                json.dumps(session_data)
            )
            return True
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            return False
    
    def delete_session(self, session_id):
        """Delete session"""
        if not self.redis_client or not session_id:
            return False
        
        session_key = f"{self.prefix}{session_id}"
        
        try:
            self.redis_client.delete(session_key)
            return True
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions (called by background task)"""
        if not self.redis_client:
            return 0
        
        try:
            pattern = f"{self.prefix}*"
            keys = self.redis_client.keys(pattern)
            
            expired_count = 0
            for key in keys:
                ttl = self.redis_client.ttl(key)
                if ttl == -2:  # Key doesn't exist
                    expired_count += 1
            
            return expired_count
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
            return 0

class CacheManager:
    """Redis-based caching utilities"""
    
    def __init__(self, redis_client, prefix='lexai_cache:'):
        self.redis_client = redis_client
        self.prefix = prefix
        self.default_ttl = 3600  # 1 hour
    
    def get(self, key):
        """Get cached value"""
        if not self.redis_client:
            return None
        
        cache_key = f"{self.prefix}{key}"
        
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"Error getting cached value: {e}")
        
        return None
    
    def set(self, key, value, ttl=None):
        """Set cached value"""
        if not self.redis_client:
            return False
        
        cache_key = f"{self.prefix}{key}"
        
        try:
            self.redis_client.setex(
                cache_key,
                ttl or self.default_ttl,
                json.dumps(value)
            )
            return True
        except Exception as e:
            logger.error(f"Error setting cached value: {e}")
            return False
    
    def delete(self, key):
        """Delete cached value"""
        if not self.redis_client:
            return False
        
        cache_key = f"{self.prefix}{key}"
        
        try:
            self.redis_client.delete(cache_key)
            return True
        except Exception as e:
            logger.error(f"Error deleting cached value: {e}")
            return False
    
    def clear_pattern(self, pattern):
        """Clear all keys matching pattern"""
        if not self.redis_client:
            return 0
        
        cache_pattern = f"{self.prefix}{pattern}"
        
        try:
            keys = self.redis_client.keys(cache_pattern)
            if keys:
                self.redis_client.delete(*keys)
            return len(keys)
        except Exception as e:
            logger.error(f"Error clearing cache pattern: {e}")
            return 0

def audit_log(action, resource_type, resource_id=None, user_id=None, 
              old_values=None, new_values=None, ip_address=None, 
              user_agent=None, success=True, error_message=None):
    """Create audit log entry"""
    try:
        log_entry = AuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            old_values=json.dumps(old_values) if old_values else None,
            new_values=json.dumps(new_values) if new_values else None,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message
        )
        
        db.session.add(log_entry)
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Error creating audit log: {e}")
        db.session.rollback()

# Initialize database manager
db_manager = DatabaseManager()

# Legacy compatibility functions
def init_db(app):
    """Legacy compatibility function"""
    db_manager.init_app(app)

def get_client_data(client_id):
    """Legacy compatibility - get client data"""
    client = Client.query.filter_by(id=client_id).first()
    if not client:
        return None
    
    return {
        'info': client.to_dict(),
        'history': [],  # Legacy conversation data
        'documents': [doc.to_dict() for doc in client.documents]
    }