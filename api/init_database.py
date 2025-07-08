#!/usr/bin/env python3
"""
Database Initialization Script for LexAI Practice Partner
Creates sample data for testing time tracking and billing integration
"""

import os
import sys
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from models import (
    db, User, Client, Case, TimeEntry, Invoice, Tag,
    UserRole, CaseStatus, TimeEntryStatus, InvoiceStatus
)
from database import DatabaseManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_app():
    """Create Flask app for database initialization"""
    app = Flask(__name__)
    
    # Configure database
    database_url = os.getenv('DATABASE_URL') or 'sqlite:///lexai_platform.db'
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database
    db_manager = DatabaseManager(app)
    
    return app

def init_sample_data():
    """Create sample data for testing"""
    print("Creating sample data...")
    
    try:
        # Create sample users
        admin_user = User.query.filter_by(email='admin@lexai.com').first()
        if not admin_user:
            admin_user = User(
                email='admin@lexai.com',
                first_name='Admin',
                last_name='User',
                role=UserRole.ADMIN,
                firm_name='LexAI Demo Firm',
                is_active=True,
                email_verified=True,
                hourly_rate=Decimal('350.00')
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            print("✓ Created admin user")
        
        # Create sample attorney
        attorney_user = User.query.filter_by(email='attorney@lexai.com').first()
        if not attorney_user:
            attorney_user = User(
                email='attorney@lexai.com',
                first_name='John',
                last_name='Attorney',
                role=UserRole.PARTNER,
                firm_name='LexAI Demo Firm',
                is_active=True,
                email_verified=True,
                hourly_rate=Decimal('450.00'),
                bar_number='BAR123456'
            )
            attorney_user.set_password('attorney123')
            db.session.add(attorney_user)
            print("✓ Created attorney user")
        
        db.session.flush()  # Get user IDs
        
        # Create sample clients
        clients_data = [
            {
                'client_type': 'individual',
                'first_name': 'John',
                'last_name': 'Smith',
                'email': 'john.smith@email.com',
                'phone': '(555) 123-4567',
                'address_line1': '123 Main Street',
                'city': 'Anytown',
                'state': 'CA',
                'zip_code': '90210',
                'billing_rate': Decimal('350.00'),
                'created_by': admin_user.id
            },
            {
                'client_type': 'business',
                'company_name': 'ABC Corporation',
                'email': 'legal@abccorp.com',
                'phone': '(555) 987-6543',
                'address_line1': '456 Business Ave',
                'city': 'Corporate City',
                'state': 'NY',
                'zip_code': '10001',
                'tax_id': '12-3456789',
                'website': 'https://abccorp.com',
                'industry': 'Technology',
                'billing_rate': Decimal('375.00'),
                'created_by': admin_user.id
            },
            {
                'client_type': 'individual',
                'first_name': 'Jane',
                'last_name': 'Doe',
                'email': 'jane.doe@email.com',
                'phone': '(555) 456-7890',
                'address_line1': '789 Oak Street',
                'city': 'Hometown',
                'state': 'TX',
                'zip_code': '75001',
                'billing_rate': Decimal('325.00'),
                'created_by': admin_user.id
            }
        ]
        
        created_clients = []
        for client_data in clients_data:
            existing_client = Client.query.filter_by(
                email=client_data['email']
            ).first()
            
            if not existing_client:
                client = Client(**client_data)
                db.session.add(client)
                created_clients.append(client)
        
        db.session.flush()  # Get client IDs
        print(f"✓ Created {len(created_clients)} clients")
        
        # Create sample cases
        cases_data = [
            {
                'case_number': 'CASE-2025-001',
                'title': 'Smith vs. Jones Divorce Settlement',
                'description': 'Divorce proceeding with asset division and custody arrangements',
                'practice_area': 'Family Law',
                'case_type': 'Divorce',
                'status': CaseStatus.ACTIVE,
                'date_opened': date(2025, 1, 15),
                'estimated_hours': Decimal('40.0'),
                'hourly_rate': Decimal('350.00'),
                'client_id': created_clients[0].id if created_clients else None,
                'primary_attorney_id': admin_user.id
            },
            {
                'case_number': 'CASE-2025-002',
                'title': 'ABC Corp Contract Review',
                'description': 'Review and negotiation of software licensing agreements',
                'practice_area': 'Corporate Law',
                'case_type': 'Contract Review',
                'status': CaseStatus.ACTIVE,
                'date_opened': date(2025, 2, 1),
                'estimated_hours': Decimal('25.0'),
                'hourly_rate': Decimal('375.00'),
                'client_id': created_clients[1].id if len(created_clients) > 1 else None,
                'primary_attorney_id': attorney_user.id
            },
            {
                'case_number': 'CASE-2025-003',
                'title': 'Jane Doe Personal Injury Claim',
                'description': 'Motor vehicle accident personal injury claim',
                'practice_area': 'Personal Injury',
                'case_type': 'Personal Injury',
                'status': CaseStatus.ACTIVE,
                'date_opened': date(2025, 1, 20),
                'estimated_hours': Decimal('60.0'),
                'hourly_rate': Decimal('325.00'),
                'client_id': created_clients[2].id if len(created_clients) > 2 else None,
                'primary_attorney_id': admin_user.id
            }
        ]
        
        created_cases = []
        for case_data in cases_data:
            if case_data['client_id']:  # Only create if we have a client
                existing_case = Case.query.filter_by(
                    case_number=case_data['case_number']
                ).first()
                
                if not existing_case:
                    case = Case(**case_data)
                    db.session.add(case)
                    created_cases.append(case)
        
        db.session.flush()  # Get case IDs
        print(f"✓ Created {len(created_cases)} cases")
        
        # Create sample time entries
        time_entries_data = [
            {
                'description': 'Initial client consultation and case review',
                'hours': Decimal('2.5'),
                'hourly_rate': Decimal('350.00'),
                'amount': Decimal('875.00'),
                'billable': True,
                'status': TimeEntryStatus.APPROVED,
                'date': date(2025, 7, 8),
                'user_id': admin_user.id,
                'case_id': created_cases[0].id if created_cases else None,
                'start_time': datetime(2025, 7, 8, 9, 0, tzinfo=timezone.utc),
                'end_time': datetime(2025, 7, 8, 11, 30, tzinfo=timezone.utc)
            },
            {
                'description': 'Legal research on contract law precedents',
                'hours': Decimal('4.0'),
                'hourly_rate': Decimal('375.00'),
                'amount': Decimal('1500.00'),
                'billable': True,
                'status': TimeEntryStatus.APPROVED,
                'date': date(2025, 7, 6),
                'user_id': attorney_user.id,
                'case_id': created_cases[1].id if len(created_cases) > 1 else None,
                'start_time': datetime(2025, 7, 6, 10, 0, tzinfo=timezone.utc),
                'end_time': datetime(2025, 7, 6, 14, 0, tzinfo=timezone.utc)
            },
            {
                'description': 'Document preparation and review',
                'hours': Decimal('3.0'),
                'hourly_rate': Decimal('350.00'),
                'amount': Decimal('1050.00'),
                'billable': True,
                'status': TimeEntryStatus.SUBMITTED,
                'date': date(2025, 7, 5),
                'user_id': admin_user.id,
                'case_id': created_cases[0].id if created_cases else None,
                'start_time': datetime(2025, 7, 5, 13, 0, tzinfo=timezone.utc),
                'end_time': datetime(2025, 7, 5, 16, 0, tzinfo=timezone.utc)
            },
            {
                'description': 'Client meeting and settlement negotiation',
                'hours': Decimal('1.5'),
                'hourly_rate': Decimal('325.00'),
                'amount': Decimal('487.50'),
                'billable': True,
                'status': TimeEntryStatus.APPROVED,
                'date': date(2025, 7, 7),
                'user_id': admin_user.id,
                'case_id': created_cases[2].id if len(created_cases) > 2 else None,
                'start_time': datetime(2025, 7, 7, 14, 0, tzinfo=timezone.utc),
                'end_time': datetime(2025, 7, 7, 15, 30, tzinfo=timezone.utc)
            },
            {
                'description': 'Administrative tasks and file organization',
                'hours': Decimal('1.0'),
                'hourly_rate': Decimal('350.00'),
                'amount': Decimal('350.00'),
                'billable': False,
                'status': TimeEntryStatus.DRAFT,
                'date': date(2025, 7, 8),
                'user_id': admin_user.id,
                'case_id': None,
                'start_time': datetime(2025, 7, 8, 16, 0, tzinfo=timezone.utc),
                'end_time': datetime(2025, 7, 8, 17, 0, tzinfo=timezone.utc)
            }
        ]
        
        created_entries = 0
        for entry_data in time_entries_data:
            if not entry_data['case_id'] and entry_data['billable']:
                continue  # Skip billable entries without cases
                
            entry = TimeEntry(**entry_data)
            db.session.add(entry)
            created_entries += 1
        
        print(f"✓ Created {created_entries} time entries")
        
        # Create sample invoice
        if created_cases and created_clients:
            existing_invoice = Invoice.query.filter_by(
                invoice_number='INV-2025-001'
            ).first()
            
            if not existing_invoice:
                invoice = Invoice(
                    invoice_number='INV-2025-001',
                    subject='Legal Services - Smith vs. Jones',
                    description='Legal consultation and document review services',
                    subtotal=Decimal('1925.00'),
                    tax_rate=Decimal('0.08'),
                    tax_amount=Decimal('154.00'),
                    total_amount=Decimal('2079.00'),
                    amount_paid=Decimal('0.00'),
                    status=InvoiceStatus.SENT,
                    issue_date=date(2025, 7, 8),
                    due_date=date(2025, 8, 7),
                    payment_terms='Net 30',
                    client_id=created_clients[0].id,
                    created_by=admin_user.id
                )
                db.session.add(invoice)
                print("✓ Created sample invoice")
        
        # Commit all changes
        db.session.commit()
        print("\n✅ Sample data created successfully!")
        
        # Print summary
        print("\n📊 Database Summary:")
        print(f"  Users: {User.query.count()}")
        print(f"  Clients: {Client.query.count()}")
        print(f"  Cases: {Case.query.count()}")
        print(f"  Time Entries: {TimeEntry.query.count()}")
        print(f"  Invoices: {Invoice.query.count()}")
        
        print("\n🔐 Test Credentials:")
        print("  Admin: admin@lexai.com / admin123")
        print("  Attorney: attorney@lexai.com / attorney123")
        
    except Exception as e:
        print(f"❌ Error creating sample data: {e}")
        db.session.rollback()
        raise

def main():
    """Main initialization function"""
    print("🚀 Initializing LexAI Database...")
    
    app = create_app()
    
    with app.app_context():
        # Create tables
        print("📋 Creating database tables...")
        db.create_all()
        print("✓ Tables created")
        
        # Create sample data
        init_sample_data()
        
        print("\n🎉 Database initialization complete!")
        print("\nYou can now:")
        print("  1. Start the Flask application")
        print("  2. Access time tracking at /time-tracking")
        print("  3. Access billing dashboard at /billing")
        print("  4. Test the APIs with real database data")

if __name__ == '__main__':
    main()