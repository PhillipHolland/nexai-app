#!/usr/bin/env python3
"""
LexAI Practice Partner - Database Initialization Script
Creates tables and populates with initial data for development and testing
"""

import os
import sys
from datetime import datetime, date, timezone
from decimal import Decimal

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
# Import database components with fallback
try:
    from database import DatabaseManager, db_manager
except ImportError:
    # Fallback for development without all dependencies
    db_manager = None
try:
    from models import (
        db, User, Client, Case, Task, Document, TimeEntry, Invoice, Expense, 
        CalendarEvent, Tag, AuditLog, Session, UserRole, CaseStatus, TaskStatus, 
        TaskPriority, DocumentStatus, TimeEntryStatus, InvoiceStatus
    )
except ImportError:
    # For development, create minimal imports
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()
    print("Warning: Using minimal database setup for development")

def create_app():
    """Create Flask app for database initialization"""
    app = Flask(__name__)
    
    # Database configuration
    database_url = os.getenv('DATABASE_URL') or 'sqlite:///lexai_development.db'
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'development-key-only'
    
    # Initialize database manager
    db_manager.init_app(app)
    
    return app

def create_sample_users():
    """Create sample users for development"""
    users = [
        {
            'email': 'admin@lexai.com',
            'first_name': 'System',
            'last_name': 'Administrator',
            'role': UserRole.ADMIN,
            'firm_name': 'LexAI Practice Partner',
            'is_active': True,
            'email_verified': True,
            'password': 'admin123'
        },
        {
            'email': 'sarah.johnson@lexai.com',
            'first_name': 'Sarah',
            'last_name': 'Johnson',
            'role': UserRole.PARTNER,
            'firm_name': 'LexAI Practice Partner',
            'bar_number': 'CA12345',
            'practice_areas': '["litigation", "corporate", "family"]',
            'hourly_rate': Decimal('450.00'),
            'is_active': True,
            'email_verified': True,
            'password': 'sarah123'
        },
        {
            'email': 'michael.chen@lexai.com',
            'first_name': 'Michael',
            'last_name': 'Chen',
            'role': UserRole.ASSOCIATE,
            'firm_name': 'LexAI Practice Partner',
            'bar_number': 'CA12346',
            'practice_areas': '["corporate", "real_estate", "immigration"]',
            'hourly_rate': Decimal('325.00'),
            'is_active': True,
            'email_verified': True,
            'password': 'michael123'
        },
        {
            'email': 'emily.rodriguez@lexai.com',
            'first_name': 'Emily',
            'last_name': 'Rodriguez',
            'role': UserRole.ASSOCIATE,
            'firm_name': 'LexAI Practice Partner',
            'bar_number': 'CA12347',
            'practice_areas': '["family", "estate", "personal_injury"]',
            'hourly_rate': Decimal('300.00'),
            'is_active': True,
            'email_verified': True,
            'password': 'emily123'
        },
        {
            'email': 'david.kim@lexai.com',
            'first_name': 'David',
            'last_name': 'Kim',
            'role': UserRole.PARALEGAL,
            'firm_name': 'LexAI Practice Partner',
            'practice_areas': '["litigation", "corporate"]',
            'hourly_rate': Decimal('150.00'),
            'is_active': True,
            'email_verified': True,
            'password': 'david123'
        }
    ]
    
    created_users = []
    for user_data in users:
        # Check if user already exists
        existing_user = User.query.filter_by(email=user_data['email']).first()
        if not existing_user:
            password = user_data.pop('password')
            user = User(**user_data)
            user.set_password(password)
            db.session.add(user)
            created_users.append(user)
            print(f"Created user: {user.email}")
        else:
            created_users.append(existing_user)
            print(f"User already exists: {existing_user.email}")
    
    return created_users

def create_sample_clients(users):
    """Create sample clients"""
    sarah = next(u for u in users if u.first_name == 'Sarah')
    michael = next(u for u in users if u.first_name == 'Michael')
    emily = next(u for u in users if u.first_name == 'Emily')
    
    clients = [
        {
            'client_type': 'individual',
            'first_name': 'John',
            'last_name': 'Smith',
            'email': 'john.smith@email.com',
            'phone': '(555) 123-4567',
            'address_line1': '123 Main Street',
            'city': 'Los Angeles',
            'state': 'CA',
            'zip_code': '90210',
            'status': 'active',
            'source': 'referral',
            'billing_rate': Decimal('450.00'),
            'created_by': sarah.id
        },
        {
            'client_type': 'business',
            'company_name': 'ABC Corporation',
            'email': 'legal@abccorp.com',
            'phone': '(555) 234-5678',
            'address_line1': '456 Business Ave',
            'city': 'San Francisco',
            'state': 'CA',
            'zip_code': '94102',
            'tax_id': '12-3456789',
            'website': 'https://abccorp.com',
            'industry': 'Technology',
            'status': 'active',
            'source': 'website',
            'billing_rate': Decimal('500.00'),
            'created_by': michael.id
        },
        {
            'client_type': 'business',
            'company_name': 'Tech Startup Inc.',
            'email': 'founders@techstartup.com',
            'phone': '(555) 345-6789',
            'address_line1': '789 Innovation Blvd',
            'city': 'Palo Alto',
            'state': 'CA',
            'zip_code': '94301',
            'tax_id': '98-7654321',
            'website': 'https://techstartup.com',
            'industry': 'Software',
            'status': 'active',
            'source': 'referral',
            'billing_rate': Decimal('400.00'),
            'created_by': michael.id
        },
        {
            'client_type': 'individual',
            'first_name': 'Jane',
            'last_name': 'Doe',
            'email': 'jane.doe@email.com',
            'phone': '(555) 456-7890',
            'address_line1': '321 Oak Street',
            'city': 'Beverly Hills',
            'state': 'CA',
            'zip_code': '90210',
            'status': 'active',
            'source': 'website',
            'billing_rate': Decimal('300.00'),
            'created_by': emily.id
        }
    ]
    
    created_clients = []
    for client_data in clients:
        client = Client(**client_data)
        db.session.add(client)
        created_clients.append(client)
        display_name = client_data.get('company_name') or f"{client_data.get('first_name')} {client_data.get('last_name')}"
        print(f"Created client: {display_name}")
    
    return created_clients

def create_sample_cases(users, clients):
    """Create sample cases"""
    sarah = next(u for u in users if u.first_name == 'Sarah')
    michael = next(u for u in users if u.first_name == 'Michael')
    emily = next(u for u in users if u.first_name == 'Emily')
    
    john_smith = next(c for c in clients if c.first_name == 'John')
    abc_corp = next(c for c in clients if c.company_name == 'ABC Corporation')
    tech_startup = next(c for c in clients if c.company_name == 'Tech Startup Inc.')
    jane_doe = next(c for c in clients if c.first_name == 'Jane')
    
    cases = [
        {
            'case_number': 'CASE-2024-001',
            'title': 'Smith Divorce Proceedings',
            'description': 'Divorce and child custody case for John Smith',
            'practice_area': 'family',
            'case_type': 'Divorce',
            'status': CaseStatus.ACTIVE,
            'priority': 'high',
            'date_opened': date(2024, 1, 15),
            'estimated_hours': Decimal('50.00'),
            'hourly_rate': Decimal('450.00'),
            'client_id': john_smith.id,
            'primary_attorney_id': sarah.id
        },
        {
            'case_number': 'CASE-2024-002',
            'title': 'ABC Corp M&A Transaction',
            'description': 'Merger and acquisition due diligence for ABC Corporation',
            'practice_area': 'corporate',
            'case_type': 'M&A',
            'status': CaseStatus.ACTIVE,
            'priority': 'high',
            'date_opened': date(2024, 1, 10),
            'estimated_hours': Decimal('100.00'),
            'hourly_rate': Decimal('500.00'),
            'client_id': abc_corp.id,
            'primary_attorney_id': michael.id
        },
        {
            'case_number': 'CASE-2024-003',
            'title': 'Tech Startup Incorporation',
            'description': 'Business formation and incorporation for tech startup',
            'practice_area': 'corporate',
            'case_type': 'Incorporation',
            'status': CaseStatus.ACTIVE,
            'priority': 'medium',
            'date_opened': date(2024, 1, 20),
            'estimated_hours': Decimal('25.00'),
            'hourly_rate': Decimal('400.00'),
            'client_id': tech_startup.id,
            'primary_attorney_id': michael.id
        },
        {
            'case_number': 'CASE-2024-004',
            'title': 'Doe Estate Planning',
            'description': 'Will and trust preparation for Jane Doe',
            'practice_area': 'estate',
            'case_type': 'Estate Planning',
            'status': CaseStatus.ACTIVE,
            'priority': 'medium',
            'date_opened': date(2024, 1, 25),
            'estimated_hours': Decimal('15.00'),
            'hourly_rate': Decimal('300.00'),
            'client_id': jane_doe.id,
            'primary_attorney_id': emily.id
        }
    ]
    
    created_cases = []
    for case_data in cases:
        case = Case(**case_data)
        db.session.add(case)
        created_cases.append(case)
        print(f"Created case: {case.case_number} - {case.title}")
    
    return created_cases

def create_sample_tasks(users, cases, clients):
    """Create sample tasks"""
    sarah = next(u for u in users if u.first_name == 'Sarah')
    michael = next(u for u in users if u.first_name == 'Michael')
    emily = next(u for u in users if u.first_name == 'Emily')
    david = next(u for u in users if u.first_name == 'David')
    
    smith_case = next(c for c in cases if c.case_number == 'CASE-2024-001')
    abc_case = next(c for c in cases if c.case_number == 'CASE-2024-002')
    startup_case = next(c for c in cases if c.case_number == 'CASE-2024-003')
    
    tasks = [
        {
            'title': 'Review Discovery Documents',
            'description': 'Analyze and categorize discovery documents for Smith divorce case',
            'status': TaskStatus.TODO,
            'priority': TaskPriority.HIGH,
            'due_date': date(2024, 1, 30),
            'estimated_hours': Decimal('8.00'),
            'assignee_id': sarah.id,
            'case_id': smith_case.id,
            'client_id': smith_case.client_id,
            'created_by': sarah.id
        },
        {
            'title': 'Draft Employment Contract',
            'description': 'Create employment agreement for senior developer position',
            'status': TaskStatus.IN_PROGRESS,
            'priority': TaskPriority.MEDIUM,
            'due_date': date(2024, 1, 28),
            'estimated_hours': Decimal('4.00'),
            'assignee_id': michael.id,
            'case_id': startup_case.id,
            'client_id': startup_case.client_id,
            'created_by': michael.id
        },
        {
            'title': 'Prepare Motion for Summary Judgment',
            'description': 'Draft and file motion for summary judgment in Smith case',
            'status': TaskStatus.REVIEW,
            'priority': TaskPriority.HIGH,
            'due_date': date(2024, 2, 5),
            'estimated_hours': Decimal('12.00'),
            'assignee_id': sarah.id,
            'case_id': smith_case.id,
            'client_id': smith_case.client_id,
            'created_by': sarah.id
        },
        {
            'title': 'Due Diligence Review',
            'description': 'Review financial documents for ABC Corp M&A transaction',
            'status': TaskStatus.IN_PROGRESS,
            'priority': TaskPriority.HIGH,
            'due_date': date(2024, 2, 1),
            'estimated_hours': Decimal('20.00'),
            'assignee_id': david.id,
            'case_id': abc_case.id,
            'client_id': abc_case.client_id,
            'created_by': michael.id
        },
        {
            'title': 'Client Meeting Preparation',
            'description': 'Prepare for quarterly business review with ABC Corp',
            'status': TaskStatus.DONE,
            'priority': TaskPriority.MEDIUM,
            'due_date': date(2024, 1, 25),
            'completed_date': datetime(2024, 1, 24, 14, 30, tzinfo=timezone.utc),
            'estimated_hours': Decimal('2.00'),
            'actual_hours': Decimal('1.50'),
            'assignee_id': michael.id,
            'case_id': abc_case.id,
            'client_id': abc_case.client_id,
            'created_by': michael.id
        }
    ]
    
    created_tasks = []
    for task_data in tasks:
        task = Task(**task_data)
        db.session.add(task)
        created_tasks.append(task)
        print(f"Created task: {task.title}")
    
    return created_tasks

def create_sample_calendar_events(users, cases, clients):
    """Create sample calendar events"""
    sarah = next(u for u in users if u.first_name == 'Sarah')
    michael = next(u for u in users if u.first_name == 'Michael')
    emily = next(u for u in users if u.first_name == 'Emily')
    
    smith_case = next(c for c in cases if c.case_number == 'CASE-2024-001')
    abc_case = next(c for c in cases if c.case_number == 'CASE-2024-002')
    
    events = [
        {
            'title': 'Client Meeting - Smith Case',
            'description': 'Initial consultation regarding divorce proceedings',
            'event_type': 'meeting',
            'location': 'Conference Room A',
            'start_datetime': datetime(2024, 1, 30, 9, 0, tzinfo=timezone.utc),
            'end_datetime': datetime(2024, 1, 30, 10, 0, tzinfo=timezone.utc),
            'case_id': smith_case.id,
            'client_id': smith_case.client_id,
            'created_by': sarah.id
        },
        {
            'title': 'Court Hearing - Smith v. Smith',
            'description': 'Preliminary hearing for divorce case',
            'event_type': 'court',
            'location': 'Superior Court, Room 205',
            'start_datetime': datetime(2024, 2, 5, 14, 0, tzinfo=timezone.utc),
            'end_datetime': datetime(2024, 2, 5, 16, 0, tzinfo=timezone.utc),
            'case_id': smith_case.id,
            'client_id': smith_case.client_id,
            'created_by': sarah.id
        },
        {
            'title': 'ABC Corp Board Meeting',
            'description': 'Attend board meeting for M&A discussion',
            'event_type': 'meeting',
            'location': 'ABC Corp Headquarters',
            'start_datetime': datetime(2024, 1, 28, 10, 0, tzinfo=timezone.utc),
            'end_datetime': datetime(2024, 1, 28, 12, 0, tzinfo=timezone.utc),
            'case_id': abc_case.id,
            'client_id': abc_case.client_id,
            'created_by': michael.id
        },
        {
            'title': 'Deposition Preparation',
            'description': 'Prepare witness for upcoming deposition',
            'event_type': 'preparation',
            'location': 'Office',
            'start_datetime': datetime(2024, 2, 1, 13, 0, tzinfo=timezone.utc),
            'end_datetime': datetime(2024, 2, 1, 15, 0, tzinfo=timezone.utc),
            'case_id': smith_case.id,
            'client_id': smith_case.client_id,
            'created_by': sarah.id
        }
    ]
    
    created_events = []
    for event_data in events:
        event = CalendarEvent(**event_data)
        db.session.add(event)
        created_events.append(event)
        print(f"Created calendar event: {event.title}")
    
    return created_events

def main():
    """Main initialization function"""
    print("🏛️ LexAI Practice Partner - Database Initialization")
    print("=" * 50)
    
    # Create Flask app
    app = create_app()
    
    with app.app_context():
        try:
            print("Creating database tables...")
            db.create_all()
            print("✅ Database tables created successfully")
            
            print("\nCreating sample data...")
            
            # Create users
            users = create_sample_users()
            db.session.commit()
            print(f"✅ Created {len(users)} users")
            
            # Create clients
            clients = create_sample_clients(users)
            db.session.commit()
            print(f"✅ Created {len(clients)} clients")
            
            # Create cases
            cases = create_sample_cases(users, clients)
            db.session.commit()
            print(f"✅ Created {len(cases)} cases")
            
            # Create tasks
            tasks = create_sample_tasks(users, cases, clients)
            db.session.commit()
            print(f"✅ Created {len(tasks)} tasks")
            
            # Create calendar events
            events = create_sample_calendar_events(users, cases, clients)
            db.session.commit()
            print(f"✅ Created {len(events)} calendar events")
            
            print("\n🎉 Database initialization completed successfully!")
            print("\nSample login credentials:")
            print("- Admin: admin@lexai.com / admin123")
            print("- Sarah Johnson: sarah.johnson@lexai.com / sarah123")
            print("- Michael Chen: michael.chen@lexai.com / michael123")
            print("- Emily Rodriguez: emily.rodriguez@lexai.com / emily123")
            print("- David Kim: david.kim@lexai.com / david123")
            
        except Exception as e:
            print(f"❌ Error during initialization: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    main()