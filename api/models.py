"""
LexAI Practice Partner - Database Models
Comprehensive database models for legal practice management
"""

from datetime import datetime, timezone
from decimal import Decimal
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Numeric
import enum
import uuid
import json

db = SQLAlchemy()

# Enum classes for database constraints
class UserRole(enum.Enum):
    CLIENT = "client"           # Read-only access to own cases/documents, can upload docs & pay invoices
    PARALEGAL = "paralegal"     # Full billing access, case management for assigned cases
    ATTORNEY = "attorney"       # Full practice management, case oversight, strategic decisions
    ADMIN = "admin"             # Full system access, user management, firm settings
    
    # Legacy roles for backward compatibility
    PARTNER = "admin"           # Maps to admin
    ASSOCIATE = "attorney"      # Maps to attorney  
    STAFF = "paralegal"         # Maps to paralegal

class CaseStatus(enum.Enum):
    ACTIVE = "active"
    PENDING = "pending"
    CLOSED = "closed"
    ON_HOLD = "on_hold"

class TaskStatus(enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"

class TaskPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class DocumentStatus(enum.Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    FINAL = "final"
    ARCHIVED = "archived"

class TimeEntryStatus(enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    BILLED = "billed"

class InvoiceStatus(enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

class SubscriptionStatus(enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    PAUSED = "paused"
    TRIAL = "trial"

class BillingCycle(enum.Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"

class PaymentStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

# Association Tables for Many-to-Many Relationships
case_attorneys = db.Table('case_attorneys',
    db.Column('case_id', db.String(36), db.ForeignKey('cases.id'), primary_key=True),
    db.Column('user_id', db.String(36), db.ForeignKey('users.id'), primary_key=True)
)

document_tags = db.Table('document_tags',
    db.Column('document_id', db.String(36), db.ForeignKey('documents.id'), primary_key=True),
    db.Column('tag_id', db.String(36), db.ForeignKey('tags.id'), primary_key=True)
)

task_tags = db.Table('task_tags',
    db.Column('task_id', db.String(36), db.ForeignKey('tasks.id'), primary_key=True),
    db.Column('tag_id', db.String(36), db.ForeignKey('tags.id'), primary_key=True)
)

# User Model with Authentication
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.ASSOCIATE)
    firm_name = db.Column(db.String(255))
    bar_number = db.Column(db.String(50))
    
    # 2FA Settings
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(32))
    backup_codes = db.Column(db.Text)  # JSON array of backup codes
    
    # Account Status
    is_active = db.Column(db.Boolean, default=True)
    email_verified = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime(timezone=True))
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime(timezone=True))
    
    # Profile Information
    profile_image_url = db.Column(db.String(500))
    bio = db.Column(db.Text)
    practice_areas = db.Column(db.Text)  # JSON array
    hourly_rate = db.Column(Numeric(10, 2))
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    created_clients = db.relationship('Client', backref='created_by_user', lazy='dynamic')
    assigned_tasks = db.relationship('Task', backref='assignee_user', lazy='dynamic')
    time_entries = db.relationship('TimeEntry', backref='user', lazy='dynamic')
    created_documents = db.relationship('Document', backref='created_by_user', lazy='dynamic')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def generate_2fa_secret(self):
        """Generate a new 2FA secret"""
        import pyotp
        import secrets
        secret = pyotp.random_base32()
        self.two_factor_secret = secret
        return secret
    
    def get_2fa_uri(self):
        """Get 2FA provisioning URI for QR code"""
        import pyotp
        if not self.two_factor_secret:
            return None
        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.provisioning_uri(
            name=self.email,
            issuer_name="LexAI Practice Partner"
        )
    
    def verify_2fa_token(self, token):
        """Verify 2FA token"""
        import pyotp
        if not self.two_factor_secret or not self.two_factor_enabled:
            return False
        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.verify(token, valid_window=1)
    
    def generate_backup_codes(self):
        """Generate backup codes for 2FA"""
        import secrets
        codes = []
        for _ in range(8):
            code = '-'.join([secrets.token_hex(2).upper() for _ in range(2)])
            codes.append(code)
        self.backup_codes = json.dumps(codes)
        return codes
    
    def verify_backup_code(self, code):
        """Verify and consume backup code"""
        if not self.backup_codes:
            return False
        codes = json.loads(self.backup_codes)
        if code in codes:
            codes.remove(code)
            self.backup_codes = json.dumps(codes)
            return True
        return False
    
    def get_full_name(self):
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}"
    
    def get_practice_areas_list(self):
        """Get practice areas as list"""
        if self.practice_areas:
            return json.loads(self.practice_areas)
        return []
    
    def set_practice_areas(self, areas_list):
        """Set practice areas from list"""
        self.practice_areas = json.dumps(areas_list)
    
    # Role-based permission methods
    def has_role(self, *roles):
        """Check if user has any of the specified roles"""
        user_role = self.role.value
        # Handle legacy role mappings
        if user_role == "partner":
            user_role = "admin"
        elif user_role == "associate":
            user_role = "attorney"
        elif user_role == "staff":
            user_role = "paralegal"
        
        return user_role in [role.value if hasattr(role, 'value') else role for role in roles]
    
    def can_access_billing(self):
        """Check if user can access billing features"""
        return self.has_role(UserRole.PARALEGAL, UserRole.ATTORNEY, UserRole.ADMIN)
    
    def can_manage_cases(self):
        """Check if user can manage cases"""
        return self.has_role(UserRole.PARALEGAL, UserRole.ATTORNEY, UserRole.ADMIN)
    
    def can_access_all_cases(self):
        """Check if user can access all cases (vs. only assigned ones)"""
        return self.has_role(UserRole.ATTORNEY, UserRole.ADMIN)
    
    def can_manage_users(self):
        """Check if user can manage other users"""
        return self.has_role(UserRole.ADMIN)
    
    def can_access_analytics(self):
        """Check if user can access firm analytics"""
        return self.has_role(UserRole.ATTORNEY, UserRole.ADMIN)
    
    def can_modify_firm_settings(self):
        """Check if user can modify firm-wide settings"""
        return self.has_role(UserRole.ADMIN)
    
    def can_access_case(self, case_id):
        """Check if user can access a specific case"""
        if self.has_role(UserRole.CLIENT):
            # Clients can only access their own cases
            # This would need to be implemented based on a client-user relationship
            return False  # TODO: Implement client-case access check
        elif self.has_role(UserRole.PARALEGAL):
            # Paralegals can access assigned cases
            return str(case_id) in [str(case.id) for case in self.cases]
        else:
            # Attorneys and admins can access all cases
            return self.can_access_all_cases()
    
    def get_dashboard_route(self):
        """Get the appropriate dashboard route for user's role"""
        if self.has_role(UserRole.CLIENT):
            return '/client-portal'
        elif self.has_role(UserRole.PARALEGAL):
            return '/paralegal-dashboard'
        elif self.has_role(UserRole.ATTORNEY):
            return '/dashboard'
        elif self.has_role(UserRole.ADMIN):
            return '/admin-dashboard'
        else:
            return '/dashboard'  # Default fallback
    
    def get_allowed_features(self):
        """Get list of features this user can access"""
        features = []
        
        if self.has_role(UserRole.CLIENT):
            features.extend(['client_portal', 'document_upload', 'invoice_payment', 'messaging'])
        
        if self.can_manage_cases():
            features.extend(['case_management', 'document_management', 'task_management', 'calendar'])
        
        if self.can_access_billing():
            features.extend(['billing', 'time_tracking', 'expense_tracking', 'invoice_management'])
        
        if self.has_role(UserRole.ATTORNEY, UserRole.ADMIN):
            features.extend(['evidence_analysis', 'legal_research', 'contract_generation'])
        
        if self.can_access_analytics():
            features.extend(['analytics', 'reporting'])
        
        if self.can_manage_users():
            features.extend(['user_management', 'firm_settings', 'subscription_management'])
        
        return features
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.get_full_name(),
            'phone': self.phone,
            'role': self.role.value,
            'firm_name': self.firm_name,
            'is_active': self.is_active,
            'dashboard_route': self.get_dashboard_route(),
            'allowed_features': self.get_allowed_features(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Client Model
class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_type = db.Column(db.String(20), nullable=False, default='individual')  # individual, business
    
    # Individual Client Fields
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    
    # Business Client Fields
    company_name = db.Column(db.String(255))
    
    # Contact Information
    email = db.Column(db.String(255), index=True)
    phone = db.Column(db.String(20))
    address_line1 = db.Column(db.String(255))
    address_line2 = db.Column(db.String(255))
    city = db.Column(db.String(100))
    state = db.Column(db.String(50))
    zip_code = db.Column(db.String(20))
    country = db.Column(db.String(100), default='United States')
    
    # Business Information
    tax_id = db.Column(db.String(50))
    website = db.Column(db.String(255))
    industry = db.Column(db.String(100))
    
    # Client Status
    status = db.Column(db.String(20), default='active')  # active, inactive, prospect
    source = db.Column(db.String(100))  # referral, website, etc.
    notes = db.Column(db.Text)
    
    # Billing Information
    billing_rate = db.Column(Numeric(10, 2))
    payment_terms = db.Column(db.String(50), default='Net 30')
    
    # Relationships
    created_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    cases = db.relationship('Case', backref='client', lazy='dynamic')
    documents = db.relationship('Document', backref='client', lazy='dynamic')
    invoices = db.relationship('Invoice', backref='client', lazy='dynamic')
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def get_display_name(self):
        """Get client display name"""
        if self.client_type == 'business':
            return self.company_name
        return f"{self.first_name} {self.last_name}"
    
    def get_full_address(self):
        """Get formatted full address"""
        parts = [self.address_line1, self.address_line2, self.city, self.state, self.zip_code]
        return ', '.join([part for part in parts if part])
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'client_type': self.client_type,
            'display_name': self.get_display_name(),
            'first_name': self.first_name,
            'last_name': self.last_name,
            'company_name': self.company_name,
            'email': self.email,
            'phone': self.phone,
            'address': self.get_full_address(),
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Case Model
class Case(db.Model):
    __tablename__ = 'cases'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    
    # Case Details
    practice_area = db.Column(db.String(100), nullable=False)
    case_type = db.Column(db.String(100))
    status = db.Column(db.Enum(CaseStatus), nullable=False, default=CaseStatus.ACTIVE)
    priority = db.Column(db.String(20), default='medium')
    
    # Court Information
    court_name = db.Column(db.String(255))
    judge_name = db.Column(db.String(255))
    court_case_number = db.Column(db.String(100))
    
    # Important Dates
    date_opened = db.Column(db.Date, nullable=False)
    date_closed = db.Column(db.Date)
    statute_of_limitations = db.Column(db.Date)
    
    # Financial Information
    estimated_hours = db.Column(Numeric(8, 2))
    hourly_rate = db.Column(Numeric(10, 2))
    flat_fee = db.Column(Numeric(10, 2))
    retainer_amount = db.Column(Numeric(10, 2))
    
    # Relationships
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'), nullable=False)
    primary_attorney_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    # Many-to-many relationship with attorneys
    attorneys = db.relationship('User', secondary=case_attorneys, backref='cases')
    
    # One-to-many relationships
    tasks = db.relationship('Task', backref='case', lazy='dynamic')
    documents = db.relationship('Document', backref='case', lazy='dynamic')
    time_entries = db.relationship('TimeEntry', backref='case', lazy='dynamic')
    calendar_events = db.relationship('CalendarEvent', backref='case', lazy='dynamic')
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'case_number': self.case_number,
            'title': self.title,
            'description': self.description,
            'practice_area': self.practice_area,
            'status': self.status.value,
            'priority': self.priority,
            'client_name': self.client.get_display_name() if self.client else None,
            'date_opened': self.date_opened.isoformat() if self.date_opened else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Task Model
class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    
    # Task Status and Priority
    status = db.Column(db.Enum(TaskStatus), nullable=False, default=TaskStatus.TODO)
    priority = db.Column(db.Enum(TaskPriority), nullable=False, default=TaskPriority.MEDIUM)
    
    # Dates
    due_date = db.Column(db.Date)
    start_date = db.Column(db.Date)
    completed_date = db.Column(db.DateTime(timezone=True))
    
    # Time Estimation
    estimated_hours = db.Column(Numeric(8, 2))
    actual_hours = db.Column(Numeric(8, 2))
    
    # Relationships
    assignee_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    case_id = db.Column(db.String(36), db.ForeignKey('cases.id'))
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'))
    created_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    # Dependencies
    parent_task_id = db.Column(db.String(36), db.ForeignKey('tasks.id'))
    subtasks = db.relationship('Task', backref=db.backref('parent_task', remote_side=[id]))
    
    # Tags (many-to-many)
    tags = db.relationship('Tag', secondary=task_tags, backref='tasks')
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status.value,
            'priority': self.priority.value,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'assignee_name': self.assignee_user.get_full_name() if self.assignee_user else None,
            'case_title': self.case.title if self.case else None,
            'client_name': self.client.get_display_name() if self.client else None,
            'tags': [tag.name for tag in self.tags],
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Document Model
class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    
    # File Information
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.BigInteger)
    mime_type = db.Column(db.String(100))
    file_hash = db.Column(db.String(64))  # SHA-256 hash for integrity
    
    # Storage Information
    storage_provider = db.Column(db.String(50), default='local')  # local, s3, gcs
    storage_path = db.Column(db.String(500), nullable=False)
    storage_bucket = db.Column(db.String(255))
    
    # Document Metadata
    document_type = db.Column(db.String(100), nullable=False)
    status = db.Column(db.Enum(DocumentStatus), nullable=False, default=DocumentStatus.DRAFT)
    version = db.Column(db.String(20), default='1.0')
    
    # Access Control
    is_confidential = db.Column(db.Boolean, default=True)
    is_privileged = db.Column(db.Boolean, default=False)
    access_level = db.Column(db.String(20), default='private')  # public, private, restricted
    
    # Relationships
    case_id = db.Column(db.String(36), db.ForeignKey('cases.id'))
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'))
    created_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    # Document versions (self-referencing)
    parent_document_id = db.Column(db.String(36), db.ForeignKey('documents.id'))
    versions = db.relationship('Document', backref=db.backref('parent_document', remote_side=[id]))
    
    # Tags (many-to-many)
    tags = db.relationship('Tag', secondary=document_tags, backref='documents')
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'filename': self.filename,
            'file_size': self.file_size,
            'document_type': self.document_type,
            'status': self.status.value,
            'version': self.version,
            'case_title': self.case.title if self.case else None,
            'client_name': self.client.get_display_name() if self.client else None,
            'tags': [tag.name for tag in self.tags],
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Time Entry Model
class TimeEntry(db.Model):
    __tablename__ = 'time_entries'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    description = db.Column(db.Text, nullable=False)
    
    # Time Information
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True))
    hours = db.Column(Numeric(8, 2), nullable=False)
    
    # Billing Information
    hourly_rate = db.Column(Numeric(10, 2), nullable=False)
    amount = db.Column(Numeric(10, 2), nullable=False)
    billable = db.Column(db.Boolean, default=True)
    
    # Status
    status = db.Column(db.Enum(TimeEntryStatus), nullable=False, default=TimeEntryStatus.DRAFT)
    
    # Relationships
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    case_id = db.Column(db.String(36), db.ForeignKey('cases.id'))
    task_id = db.Column(db.String(36), db.ForeignKey('tasks.id'))
    invoice_id = db.Column(db.String(36), db.ForeignKey('invoices.id'))
    
    # Timestamps
    date = db.Column(db.Date, nullable=False, default=datetime.now(timezone.utc).date())
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'description': self.description,
            'hours': float(self.hours),
            'hourly_rate': float(self.hourly_rate),
            'amount': float(self.amount),
            'billable': self.billable,
            'status': self.status.value,
            'date': self.date.isoformat() if self.date else None,
            'user_name': self.user.get_full_name() if self.user else None,
            'case_title': self.case.title if self.case else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Invoice Model
class Invoice(db.Model):
    __tablename__ = 'invoices'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # Invoice Details
    subject = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    
    # Financial Information
    subtotal = db.Column(Numeric(10, 2), nullable=False)
    tax_rate = db.Column(Numeric(5, 4), default=0)
    tax_amount = db.Column(Numeric(10, 2), default=0)
    total_amount = db.Column(Numeric(10, 2), nullable=False)
    amount_paid = db.Column(Numeric(10, 2), default=0)
    
    # Status and Dates
    status = db.Column(db.Enum(InvoiceStatus), nullable=False, default=InvoiceStatus.DRAFT)
    issue_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    paid_date = db.Column(db.Date)
    
    # Billing Information
    billing_address = db.Column(db.Text)
    payment_terms = db.Column(db.String(50), default='Net 30')
    notes = db.Column(db.Text)
    
    # Relationships
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'), nullable=False)
    created_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    # One-to-many relationships
    time_entries = db.relationship('TimeEntry', backref='invoice', lazy='dynamic')
    expenses = db.relationship('Expense', backref='invoice', lazy='dynamic')
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def calculate_totals(self):
        """Calculate invoice totals"""
        # Calculate subtotal from time entries and expenses
        time_total = sum(entry.amount for entry in self.time_entries if entry.billable)
        expense_total = sum(expense.amount for expense in self.expenses if expense.billable)
        
        self.subtotal = time_total + expense_total
        self.tax_amount = self.subtotal * (self.tax_rate or 0)
        self.total_amount = self.subtotal + self.tax_amount
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'invoice_number': self.invoice_number,
            'subject': self.subject,
            'subtotal': float(self.subtotal),
            'tax_amount': float(self.tax_amount),
            'total_amount': float(self.total_amount),
            'amount_paid': float(self.amount_paid),
            'status': self.status.value,
            'issue_date': self.issue_date.isoformat() if self.issue_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'client_name': self.client.get_display_name() if self.client else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Subscription Plans Model
class SubscriptionPlan(db.Model):
    __tablename__ = 'subscription_plans'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    monthly_price = db.Column(Numeric(10, 2), nullable=False)
    yearly_price = db.Column(Numeric(10, 2))
    max_cases = db.Column(db.Integer)
    max_clients = db.Column(db.Integer)
    max_storage_gb = db.Column(db.Integer)
    ai_analysis_credits = db.Column(db.Integer)
    has_billing_integration = db.Column(db.Boolean, default=False)
    has_advanced_analytics = db.Column(db.Boolean, default=False)
    has_api_access = db.Column(db.Boolean, default=False)
    has_custom_branding = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserSubscription(db.Model):
    __tablename__ = 'user_subscriptions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    plan_id = db.Column(db.String(36), db.ForeignKey('subscription_plans.id'), nullable=False)
    stripe_subscription_id = db.Column(db.String(255))
    stripe_customer_id = db.Column(db.String(255))
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    next_billing_date = db.Column(db.DateTime)
    status = db.Column(db.Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    billing_cycle = db.Column(db.Enum(BillingCycle), default=BillingCycle.MONTHLY)
    current_cases = db.Column(db.Integer, default=0)
    current_clients = db.Column(db.Integer, default=0)
    current_storage_gb = db.Column(Numeric(10, 2), default=0)
    monthly_ai_credits_used = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='subscription')
    plan = db.relationship('SubscriptionPlan', backref='subscriptions')

class PaymentRecord(db.Model):
    __tablename__ = 'payment_records'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    stripe_payment_intent_id = db.Column(db.String(255), unique=True)
    stripe_charge_id = db.Column(db.String(255))
    amount = db.Column(Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    stripe_fee = db.Column(Numeric(10, 2))
    net_amount = db.Column(Numeric(10, 2))
    payment_method_type = db.Column(db.String(50))
    last_four = db.Column(db.String(4))
    brand = db.Column(db.String(20))
    status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.PENDING)
    payment_date = db.Column(db.DateTime)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    subscription_id = db.Column(db.String(36), db.ForeignKey('user_subscriptions.id'))
    invoice_id = db.Column(db.String(36), db.ForeignKey('invoices.id'))
    description = db.Column(db.Text)
    metadata = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='payments')
    subscription = db.relationship('UserSubscription', backref='payments')
    invoice = db.relationship('Invoice', backref='payments')

class UsageLog(db.Model):
    __tablename__ = 'usage_logs'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    subscription_id = db.Column(db.String(36), db.ForeignKey('user_subscriptions.id'))
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50))
    resource_id = db.Column(db.String(36))
    quantity = db.Column(db.Integer, default=1)
    cost_credits = db.Column(db.Integer, default=0)
    metadata = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    user = db.relationship('User', backref='usage_logs')
    subscription = db.relationship('UserSubscription', backref='usage_logs')

# Expense Model
class Expense(db.Model):
    __tablename__ = 'expenses'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    description = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    
    # Financial Information
    amount = db.Column(Numeric(10, 2), nullable=False)
    billable = db.Column(db.Boolean, default=True)
    reimbursable = db.Column(db.Boolean, default=False)
    
    # Receipt Information
    receipt_filename = db.Column(db.String(255))
    receipt_url = db.Column(db.String(500))
    
    # Relationships
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    case_id = db.Column(db.String(36), db.ForeignKey('cases.id'))
    invoice_id = db.Column(db.String(36), db.ForeignKey('invoices.id'))
    
    # Timestamps
    date = db.Column(db.Date, nullable=False, default=datetime.now(timezone.utc).date())
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'description': self.description,
            'category': self.category,
            'amount': float(self.amount),
            'billable': self.billable,
            'reimbursable': self.reimbursable,
            'date': self.date.isoformat() if self.date else None,
            'user_name': self.user.get_full_name() if self.user else None,
            'case_title': self.case.title if self.case else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Calendar Event Model
class CalendarEvent(db.Model):
    __tablename__ = 'calendar_events'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    
    # Event Details
    event_type = db.Column(db.String(50), nullable=False)  # meeting, court, deadline, etc.
    location = db.Column(db.String(255))
    
    # Time Information
    start_datetime = db.Column(db.DateTime(timezone=True), nullable=False)
    end_datetime = db.Column(db.DateTime(timezone=True), nullable=False)
    all_day = db.Column(db.Boolean, default=False)
    
    # Reminders
    reminder_minutes = db.Column(db.Integer, default=15)
    reminder_sent = db.Column(db.Boolean, default=False)
    
    # Relationships
    case_id = db.Column(db.String(36), db.ForeignKey('cases.id'))
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'))
    created_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'event_type': self.event_type,
            'location': self.location,
            'start_datetime': self.start_datetime.isoformat() if self.start_datetime else None,
            'end_datetime': self.end_datetime.isoformat() if self.end_datetime else None,
            'all_day': self.all_day,
            'case_title': self.case.title if self.case else None,
            'client_name': self.client.get_display_name() if self.client else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Tag Model (for organizing documents, tasks, etc.)
class Tag(db.Model):
    __tablename__ = 'tags'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    color = db.Column(db.String(7), default='#2E4B3C')  # Hex color code
    description = db.Column(db.String(255))
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Audit Log Model for tracking all system activities
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Action Information
    action = db.Column(db.String(100), nullable=False)  # create, update, delete, login, etc.
    resource_type = db.Column(db.String(50), nullable=False)  # user, client, case, document, etc.
    resource_id = db.Column(db.String(36))
    
    # Request Information
    ip_address = db.Column(db.String(45))  # IPv6 compatible
    user_agent = db.Column(db.String(500))
    request_method = db.Column(db.String(10))
    request_path = db.Column(db.String(500))
    
    # Change Information
    old_values = db.Column(db.Text)  # JSON of old values
    new_values = db.Column(db.Text)  # JSON of new values
    
    # Additional Context
    notes = db.Column(db.Text)
    success = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text)
    
    # Relationships
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    
    # Timestamp
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'user_name': self.user.get_full_name() if self.user else 'System',
            'ip_address': self.ip_address,
            'success': self.success,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Session Model for Redis session management
class Session(db.Model):
    __tablename__ = 'sessions'
    
    id = db.Column(db.String(255), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    
    # Session Information
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    
    # Session Status
    is_active = db.Column(db.Boolean, default=True)
    last_activity = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    
    def is_expired(self):
        """Check if session is expired"""
        return datetime.now(timezone.utc) > self.expires_at
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_name': self.user.get_full_name() if self.user else None,
            'ip_address': self.ip_address,
            'is_active': self.is_active,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }