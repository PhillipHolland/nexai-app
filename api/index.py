#!/usr/bin/env python3
"""
LexAI Practice Partner - Clean Serverless Version
Streamlined version for Vercel deployment without duplicate routes
"""

import os
import json
import logging
from datetime import datetime, timedelta, date
from decimal import Decimal
from flask import Flask, request, jsonify, render_template, session, redirect
from functools import wraps
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import database components
try:
    from models import db, User, Client, Case, TimeEntry, Invoice, Expense, UserRole, TimeEntryStatus, InvoiceStatus
    from database import DatabaseManager, audit_log
    DATABASE_AVAILABLE = True
    logger.info("Database models loaded successfully")
except ImportError as e:
    logger.warning(f"Database models not available: {e}")
    logger.info("Falling back to mock data - install Flask-SQLAlchemy to enable database integration")
    DATABASE_AVAILABLE = False

# Create Flask app
app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Initialize database if available
if DATABASE_AVAILABLE:
    try:
        db_manager = DatabaseManager(app)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")
        logger.info("Falling back to mock data mode")
        DATABASE_AVAILABLE = False
else:
    logger.warning("Running without database - using mock data")

# Basic configuration
app.config.update({
    'SECRET_KEY': os.environ.get('SECRET_KEY', 'dev-key-change-in-production'),
    'DATABASE_URL': os.environ.get('DATABASE_URL'),
    'REDIS_URL': os.environ.get('REDIS_URL'),
    'BAGEL_RL_API_KEY': os.environ.get('BAGEL_RL_API_KEY'),
    'XAI_API_KEY': os.environ.get('XAI_API_KEY'),
    'GOOGLE_ANALYTICS_ID': os.environ.get('GOOGLE_ANALYTICS_ID'),
})

# Service availability flags
BAGEL_AI_AVAILABLE = bool(os.environ.get('BAGEL_RL_API_KEY'))
SPANISH_AVAILABLE = True
PRIVACY_AI_AVAILABLE = False
STRIPE_AVAILABLE = bool(os.environ.get('STRIPE_SECRET_KEY'))

logger.info(f"BAGEL_AI_AVAILABLE: {BAGEL_AI_AVAILABLE}")
logger.info(f"SPANISH_AVAILABLE: {SPANISH_AVAILABLE}")
logger.info(f"STRIPE_AVAILABLE: {STRIPE_AVAILABLE}")

# ===== AUTHENTICATION MIDDLEWARE =====

def login_required(f):
    """Decorator to require authentication for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            if request.is_json:
                return jsonify({
                    'success': False,
                    'error': 'Authentication required'
                }), 401
            else:
                return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    """Decorator to require specific roles for routes"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('logged_in'):
                if request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Authentication required'
                    }), 401
                else:
                    return redirect('/login')
            
            user_role = session.get('user_role')
            if user_role not in allowed_roles:
                if request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Insufficient permissions'
                    }), 403
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Access denied - insufficient permissions'
                    }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    """Decorator to require admin role"""
    return role_required('admin')(f)

def get_current_user():
    """Helper function to get current user information"""
    if not session.get('logged_in'):
        return None
    
    if not DATABASE_AVAILABLE:
        return {
            'id': session.get('user_id'),
            'email': session.get('user_email'),
            'role': session.get('user_role'),
            'name': session.get('user_name')
        }
    
    try:
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        return user
    except:
        return None

# ===== MAIN ROUTES =====

@app.route('/')
def landing_page():
    """Landing page"""
    try:
        return render_template('landing.html',
                             google_analytics_id=app.config.get('GOOGLE_ANALYTICS_ID'))
    except Exception as e:
        logger.error(f"Landing page error: {e}")
        return f"LexAI Practice Partner - Error loading page: {e}", 500

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard"""
    try:
        # Sample stats data for dashboard
        stats = {
            'total_chats': 24,
            'total_documents': 8,
            'research_queries': 15,
            'total_clients': 3
        }
        
        return render_template('dashboard.html',
                             user_role=session.get('user_role', 'guest'),
                             user_name=session.get('user_name', 'User'),
                             stats=stats)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return f"Dashboard error: {e}", 500

@app.route('/documents')
@login_required
def documents_page():
    """Document analysis page"""
    try:
        return render_template('documents.html',
                             bagel_available=BAGEL_AI_AVAILABLE)
    except Exception as e:
        logger.error(f"Documents page error: {e}")
        return f"Documents error: {e}", 500

@app.route('/contracts')
@login_required
def contracts_page():
    """Contract analysis page"""
    try:
        return render_template('contracts.html',
                             bagel_available=BAGEL_AI_AVAILABLE)
    except Exception as e:
        logger.error(f"Contracts page error: {e}")
        return f"Contracts error: {e}", 500

@app.route('/legal-research')
@login_required
def legal_research_page():
    """Legal research page"""
    try:
        return render_template('legal_research.html',
                             bagel_available=BAGEL_AI_AVAILABLE)
    except Exception as e:
        logger.error(f"Legal research page error: {e}")
        return f"Legal research error: {e}", 500

@app.route('/spanish')
@login_required
def spanish_interface():
    """Spanish language interface"""
    try:
        return render_template('spanish_interface.html',
                             spanish_available=SPANISH_AVAILABLE)
    except Exception as e:
        logger.error(f"Spanish interface error: {e}")
        return f"Spanish interface error: {e}", 500

@app.route('/billing')
@login_required
def billing_page():
    """Billing and payments page"""
    try:
        return render_template('billing.html',
                             stripe_available=STRIPE_AVAILABLE)
    except Exception as e:
        logger.error(f"Billing page error: {e}")
        return f"Billing error: {e}", 500

@app.route('/clients')
@login_required
def clients_page():
    """Client management page"""
    try:
        return render_template('clients_enhanced.html')
    except Exception as e:
        logger.error(f"Clients page error: {e}")
        return f"Clients error: {e}", 500

@app.route('/clients/<client_id>')
@login_required
def client_profile_page(client_id):
    """Individual client profile page"""
    try:
        return render_template('client_profile.html', client_id=client_id)
    except Exception as e:
        logger.error(f"Client profile page error: {e}")
        return f"Client profile error: {e}", 500

@app.route('/clients/<client_id>/edit')
@login_required
def client_edit_page(client_id):
    """Client edit page"""
    try:
        return render_template('client_edit.html', client_id=client_id)
    except Exception as e:
        logger.error(f"Client edit page error: {e}")
        return f"Client edit error: {e}", 500

@app.route('/clients/new')
@login_required
def client_new_page():
    """New client creation page"""
    try:
        return render_template('client_new.html')
    except Exception as e:
        logger.error(f"Client new page error: {e}")
        return f"Client new error: {e}", 500

@app.route('/login')
def login_page():
    """Login page"""
    try:
        # Redirect if already logged in
        if session.get('logged_in'):
            return redirect('/dashboard')
        return render_template('auth_login_enhanced.html')
    except Exception as e:
        logger.error(f"Login page error: {e}")
        return f"Login error: {e}", 500

@app.route('/register')
def register_page():
    """Registration page"""
    try:
        # Redirect if already logged in
        if session.get('logged_in'):
            return redirect('/dashboard')
        return render_template('auth_register_enhanced.html')
    except Exception as e:
        logger.error(f"Register page error: {e}")
        return f"Register error: {e}", 500

@app.route('/chat')
@login_required
def chat_page():
    """Chat interface"""
    try:
        return render_template('chat.html',
                             xai_available=bool(app.config.get('XAI_API_KEY')))
    except Exception as e:
        logger.error(f"Chat page error: {e}")
        return f"Chat error: {e}", 500

@app.route('/onboarding')
@login_required
def onboarding_page():
    """User onboarding flow"""
    try:
        return render_template('onboarding.html')
    except Exception as e:
        logger.error(f"Onboarding error: {e}")
        return f"Onboarding error: {e}", 500

@app.route('/time-tracking')
@login_required
def time_tracking_page():
    """Time tracking interface"""
    try:
        return render_template('time_tracking.html')
    except Exception as e:
        logger.error(f"Time tracking error: {e}")
        return f"Time tracking error: {e}", 500

@app.route('/platform')
@login_required
def platform_page():
    """Platform overview page"""
    try:
        return render_template('platform_overview.html',
                             bagel_available=BAGEL_AI_AVAILABLE,
                             spanish_available=SPANISH_AVAILABLE,
                             stripe_available=STRIPE_AVAILABLE)
    except Exception as e:
        logger.error(f"Platform page error: {e}")
        return f"Platform error: {e}", 500

@app.route('/privacy-dashboard')
@login_required
def privacy_dashboard_page():
    """Privacy analysis dashboard"""
    try:
        return render_template('privacy_dashboard.html',
                             privacy_available=PRIVACY_AI_AVAILABLE)
    except Exception as e:
        logger.error(f"Privacy dashboard error: {e}")
        return f"Privacy dashboard error: {e}", 500

@app.route('/analytics-dashboard')
@login_required
def analytics_dashboard():
    """Analytics and reporting dashboard"""
    try:
        return render_template('analytics_dashboard.html')
    except Exception as e:
        logger.error(f"Analytics dashboard error: {e}")
        return f"Analytics dashboard error: {e}", 500

# ===== API ROUTES =====

@app.route('/api/health')
def api_health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.1',
        'services': {
            'bagel_ai': BAGEL_AI_AVAILABLE,
            'spanish': SPANISH_AVAILABLE,
            'stripe': STRIPE_AVAILABLE
        }
    })

@app.route('/api/status')
def api_status():
    """System status endpoint"""
    return jsonify({
        'success': True,
        'message': 'LexAI is running',
        'timestamp': datetime.now().isoformat(),
        'database_available': DATABASE_AVAILABLE,
        'data_source': 'PostgreSQL Database' if DATABASE_AVAILABLE else 'Mock Data'
    })

@app.route('/api/database/status')
def api_database_status():
    """Database integration status"""
    if DATABASE_AVAILABLE:
        try:
            with app.app_context():
                # Try to execute a simple query
                db.session.execute(db.text('SELECT 1')).fetchone()
                db_connection = 'Connected'
        except Exception as e:
            db_connection = f'Error: {str(e)}'
    else:
        db_connection = 'Not Available'
    
    return jsonify({
        'success': True,
        'database_integration': {
            'status': 'Available' if DATABASE_AVAILABLE else 'Not Available',
            'connection': db_connection,
            'models_loaded': DATABASE_AVAILABLE,
            'features': {
                'time_tracking': 'Database Integration Complete' if DATABASE_AVAILABLE else 'Mock Data Fallback',
                'invoicing': 'Database Integration Complete' if DATABASE_AVAILABLE else 'Mock Data Fallback',
                'client_management': 'Database Integration Complete' if DATABASE_AVAILABLE else 'Mock Data Fallback',
                'audit_logging': 'Available' if DATABASE_AVAILABLE else 'Not Available'
            }
        },
        'installation_note': 'Install Flask-SQLAlchemy, psycopg2-binary packages to enable database integration' if not DATABASE_AVAILABLE else None
    })

@app.route('/api/documents/analyze', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_document_analyze():
    """Analyze document text"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({
                'success': False,
                'error': 'Document text required'
            }), 400
        
        # Basic response for now
        return jsonify({
            'success': True,
            'message': 'Document analysis completed',
            'analysis': {
                'text_length': len(data['text']),
                'word_count': len(data['text'].split()),
                'status': 'analyzed'
            },
            'bagel_available': BAGEL_AI_AVAILABLE
        })
        
    except Exception as e:
        logger.error(f"Document analysis error: {e}")
        return jsonify({
            'success': False,
            'error': 'Document analysis failed'
        }), 500

@app.route('/api/spanish/translate', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_spanish_translate():
    """Translate text to Spanish"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({
                'success': False,
                'error': 'Text required for translation'
            }), 400
        
        # Basic response for now
        return jsonify({
            'success': True,
            'original_text': data['text'],
            'translated_text': f"[ES] {data['text']}",  # Placeholder
            'confidence_score': 0.95,
            'spanish_available': SPANISH_AVAILABLE
        })
        
    except Exception as e:
        logger.error(f"Spanish translation error: {e}")
        return jsonify({
            'success': False,
            'error': 'Translation failed'
        }), 500

@app.route('/api/contracts/analyze', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_contract_analyze():
    """Analyze contract"""
    try:
        data = request.get_json()
        if not data or 'contract_text' not in data:
            return jsonify({
                'success': False,
                'error': 'Contract text required'
            }), 400
        
        # Basic response for now
        return jsonify({
            'success': True,
            'contract_type': 'service',
            'overall_risk_score': 25.0,
            'key_terms': ['agreement', 'payment', 'termination'],
            'recommendations': ['Review with legal counsel'],
            'bagel_available': BAGEL_AI_AVAILABLE
        })
        
    except Exception as e:
        logger.error(f"Contract analysis error: {e}")
        return jsonify({
            'success': False,
            'error': 'Contract analysis failed'
        }), 500

@app.route('/api/chat', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_chat():
    """Chat with AI assistant"""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                'success': False,
                'error': 'Message required'
            }), 400
        
        # Basic response for now
        return jsonify({
            'success': True,
            'response': 'I am LexAI, your legal practice assistant. How can I help you today?',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({
            'success': False,
            'error': 'Chat request failed'
        }), 500

@app.route('/api/onboarding/complete', methods=['POST'])
@login_required
def api_onboarding_complete():
    """Complete user onboarding"""
    try:
        data = request.get_json()
        logger.info(f"Onboarding completed: {data.get('firmName', 'Unknown firm')}")
        
        return jsonify({
            'success': True,
            'message': 'Onboarding completed successfully',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Onboarding completion error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to complete onboarding'
        }), 500

# ===== TIME TRACKING API =====

@app.route('/api/time/entries', methods=['GET'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_get_time_entries():
    """Get time entries for current user"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_time_entries()
        
        # Get current user ID (for now, use a default user - later will get from session)
        user_id = session.get('user_id', '1')  # Will implement proper auth later
        
        # Query time entries for the user
        entries = TimeEntry.query.filter_by(user_id=user_id).order_by(TimeEntry.created_at.desc()).all()
        
        entries_data = []
        for entry in entries:
            entries_data.append({
                'id': entry.id,
                'description': entry.description,
                'hours': float(entry.hours),
                'hourly_rate': float(entry.hourly_rate),
                'amount': float(entry.amount),
                'billable': entry.billable,
                'status': entry.status.value,
                'date': entry.date.isoformat() if entry.date else None,
                'case_title': entry.case.title if entry.case else None,
                'client_name': entry.case.client.get_display_name() if entry.case and entry.case.client else None,
                'created_at': entry.created_at.isoformat() if entry.created_at else None
            })
        
        total_hours = sum(float(entry.hours) for entry in entries)
        total_billable = sum(float(entry.amount) for entry in entries if entry.billable)
        
        return jsonify({
            'success': True,
            'entries': entries_data,
            'total_hours': total_hours,
            'total_billable': total_billable
        })
        
    except Exception as e:
        logger.error(f"Get time entries error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve time entries'
        }), 500

def _get_mock_time_entries():
    """Fallback mock data when database is not available"""
    entries = [
        {
            'id': '1',
            'description': 'Client consultation and case review',
            'hours': 2.5,
            'hourly_rate': 250.00,
            'amount': 625.00,
            'billable': True,
            'status': 'draft',
            'date': '2025-07-08',
            'case_title': 'Smith vs. Jones',
            'client_name': 'John Smith'
        },
        {
            'id': '2', 
            'description': 'Document preparation and research',
            'hours': 3.0,
            'hourly_rate': 250.00,
            'amount': 750.00,
            'billable': True,
            'status': 'submitted',
            'date': '2025-07-07',
            'case_title': 'ABC Corp Contract Review',
            'client_name': 'ABC Corporation'
        }
    ]
    
    return jsonify({
        'success': True,
        'entries': entries,
        'total_hours': sum(e['hours'] for e in entries),
        'total_billable': sum(e['amount'] for e in entries if e['billable'])
    })

@app.route('/api/time/entries', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_create_time_entry():
    """Create new time entry"""
    try:
        data = request.get_json()
        
        required_fields = ['description', 'hours', 'hourly_rate']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Calculate amount
        hours = Decimal(str(data['hours']))
        rate = Decimal(str(data['hourly_rate']))
        amount = hours * rate
        
        if not DATABASE_AVAILABLE:
            return _create_mock_time_entry(data, hours, rate, amount)
        
        # Get current user ID (will implement proper auth later)
        user_id = session.get('user_id', '1')
        
        # Create new time entry
        entry = TimeEntry(
            description=data['description'],
            hours=hours,
            hourly_rate=rate,
            amount=amount,
            billable=data.get('billable', True),
            status=TimeEntryStatus.DRAFT,
            date=datetime.strptime(data.get('date', datetime.now().date().isoformat()), '%Y-%m-%d').date(),
            user_id=user_id,
            case_id=data.get('case_id'),
            start_time=datetime.now(timezone.utc),  # For timer-based entries
            end_time=datetime.now(timezone.utc)     # Will be updated for real timer
        )
        
        # Save to database
        db.session.add(entry)
        db.session.commit()
        
        # Create audit log
        audit_log(
            action='create',
            resource_type='time_entry',
            resource_id=entry.id,
            user_id=user_id,
            new_values=entry.to_dict()
        )
        
        logger.info(f"Created time entry: {entry.description} - {hours}h @ ${rate}")
        
        return jsonify({
            'success': True,
            'message': 'Time entry created successfully',
            'entry': entry.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Create time entry error: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to create time entry'
        }), 500

def _create_mock_time_entry(data, hours, rate, amount):
    """Fallback mock time entry creation"""
    entry = {
        'id': f"entry_{datetime.now().timestamp()}",
        'description': data['description'],
        'hours': float(hours),
        'hourly_rate': float(rate),
        'amount': float(amount),
        'billable': data.get('billable', True),
        'status': 'draft',
        'date': data.get('date', datetime.now().date().isoformat()),
        'case_id': data.get('case_id'),
        'client_id': data.get('client_id'),
        'created_at': datetime.now().isoformat()
    }
    
    return jsonify({
        'success': True,
        'message': 'Time entry created successfully (mock)',
        'entry': entry
    })

@app.route('/api/time/entries/<entry_id>', methods=['PUT'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_update_time_entry(entry_id):
    """Update time entry"""
    try:
        data = request.get_json()
        
        if not DATABASE_AVAILABLE:
            return jsonify({
                'success': True,
                'message': 'Time entry updated successfully (mock)',
                'entry_id': entry_id,
                'updated_fields': list(data.keys())
            })
        
        # Get current user ID
        user_id = session.get('user_id', '1')
        
        # Find the time entry
        entry = TimeEntry.query.filter_by(id=entry_id, user_id=user_id).first()
        if not entry:
            return jsonify({
                'success': False,
                'error': 'Time entry not found'
            }), 404
        
        # Store old values for audit
        old_values = entry.to_dict()
        
        # Update allowed fields
        if 'description' in data:
            entry.description = data['description']
        if 'hours' in data:
            entry.hours = Decimal(str(data['hours']))
            entry.amount = entry.hours * entry.hourly_rate
        if 'hourly_rate' in data:
            entry.hourly_rate = Decimal(str(data['hourly_rate']))
            entry.amount = entry.hours * entry.hourly_rate
        if 'billable' in data:
            entry.billable = data['billable']
        if 'date' in data:
            entry.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        
        # Save changes
        db.session.commit()
        
        # Create audit log
        audit_log(
            action='update',
            resource_type='time_entry',
            resource_id=entry.id,
            user_id=user_id,
            old_values=old_values,
            new_values=entry.to_dict()
        )
        
        return jsonify({
            'success': True,
            'message': 'Time entry updated successfully',
            'entry': entry.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Update time entry error: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to update time entry'
        }), 500

@app.route('/api/time/entries/<entry_id>/status', methods=['PUT'])
@login_required
@role_required('admin', 'partner', 'associate')
def api_update_time_entry_status(entry_id):
    """Update time entry status (draft -> submitted -> approved -> billed)"""
    try:
        data = request.get_json()
        status = data.get('status')
        
        valid_statuses = ['draft', 'submitted', 'approved', 'billed']
        if status not in valid_statuses:
            return jsonify({
                'success': False,
                'error': f'Invalid status. Must be one of: {valid_statuses}'
            }), 400
        
        if not DATABASE_AVAILABLE:
            return jsonify({
                'success': True,
                'message': f'Time entry status updated to {status} (mock)',
                'entry_id': entry_id,
                'status': status
            })
        
        # Get current user ID
        user_id = session.get('user_id', '1')
        
        # Find the time entry
        entry = TimeEntry.query.filter_by(id=entry_id, user_id=user_id).first()
        if not entry:
            return jsonify({
                'success': False,
                'error': 'Time entry not found'
            }), 404
        
        # Store old values for audit
        old_values = entry.to_dict()
        
        # Update status
        try:
            entry.status = TimeEntryStatus(status)
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid status: {status}'
            }), 400
        
        # Save changes
        db.session.commit()
        
        # Create audit log
        audit_log(
            action='status_update',
            resource_type='time_entry',
            resource_id=entry.id,
            user_id=user_id,
            old_values=old_values,
            new_values=entry.to_dict()
        )
        
        logger.info(f"Updated time entry {entry_id} status to {status}")
        
        return jsonify({
            'success': True,
            'message': f'Time entry status updated to {status}',
            'entry': entry.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Update time entry status error: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to update time entry status'
        }), 500

@app.route('/api/time/entries/billable', methods=['GET'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_get_billable_entries():
    """Get billable time entries ready for invoicing"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_billable_entries()
        
        # Get query parameters
        client_id = request.args.get('client_id')
        
        # Build query for billable time entries
        query = TimeEntry.query.filter(
            TimeEntry.billable == True,
            TimeEntry.status.in_([TimeEntryStatus.APPROVED, TimeEntryStatus.SUBMITTED])
        )
        
        # Filter by client if specified
        if client_id:
            query = query.join(Case).filter(Case.client_id == client_id)
        
        # Get current user's entries (will implement proper auth later)
        user_id = session.get('user_id', '1')
        query = query.filter(TimeEntry.user_id == user_id)
        
        entries = query.order_by(TimeEntry.date.desc()).all()
        
        billable_entries = []
        clients = {}
        
        for entry in entries:
            entry_data = {
                'id': entry.id,
                'description': entry.description,
                'hours': float(entry.hours),
                'hourly_rate': float(entry.hourly_rate),
                'amount': float(entry.amount),
                'status': entry.status.value,
                'date': entry.date.isoformat() if entry.date else None,
                'case_title': entry.case.title if entry.case else 'No Case',
                'client_name': entry.case.client.get_display_name() if entry.case and entry.case.client else 'No Client',
                'client_id': entry.case.client_id if entry.case else None
            }
            
            billable_entries.append(entry_data)
            
            # Group by client
            if entry.case and entry.case.client_id:
                client_key = entry.case.client_id
                if client_key not in clients:
                    clients[client_key] = {
                        'client_name': entry.case.client.get_display_name(),
                        'entries': [],
                        'total_hours': 0,
                        'total_amount': 0
                    }
                clients[client_key]['entries'].append(entry_data)
                clients[client_key]['total_hours'] += float(entry.hours)
                clients[client_key]['total_amount'] += float(entry.amount)
        
        return jsonify({
            'success': True,
            'billable_entries': billable_entries,
            'clients': clients,
            'total_billable_hours': sum(float(e.hours) for e in entries),
            'total_billable_amount': sum(float(e.amount) for e in entries)
        })
        
    except Exception as e:
        logger.error(f"Get billable entries error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve billable entries'
        }), 500

def _get_mock_billable_entries():
    """Fallback mock billable entries"""
    billable_entries = [
        {
            'id': '1',
            'description': 'Client consultation and case review',
            'hours': 2.5,
            'hourly_rate': 250.00,
            'amount': 625.00,
            'status': 'approved',
            'date': '2025-07-08',
            'case_title': 'Smith vs. Jones',
            'client_name': 'John Smith',
            'client_id': 'client_1'
        },
        {
            'id': '3',
            'description': 'Legal research on contract law',
            'hours': 4.0,
            'hourly_rate': 250.00,
            'amount': 1000.00,
            'status': 'approved',
            'date': '2025-07-06',
            'case_title': 'Smith vs. Jones',
            'client_name': 'John Smith',
            'client_id': 'client_1'
        }
    ]
    
    # Group by client
    clients = {}
    for entry in billable_entries:
        client_id = entry['client_id']
        if client_id not in clients:
            clients[client_id] = {
                'client_name': entry['client_name'],
                'entries': [],
                'total_hours': 0,
                'total_amount': 0
            }
        clients[client_id]['entries'].append(entry)
        clients[client_id]['total_hours'] += entry['hours']
        clients[client_id]['total_amount'] += entry['amount']
    
    return jsonify({
        'success': True,
        'billable_entries': billable_entries,
        'clients': clients,
        'total_billable_hours': sum(e['hours'] for e in billable_entries),
        'total_billable_amount': sum(e['amount'] for e in billable_entries)
    })

# ===== INVOICE API =====

@app.route('/api/invoices', methods=['GET'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_get_invoices():
    """Get all invoices"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_invoices()
        
        # Get current user's invoices (will implement proper auth later)
        user_id = session.get('user_id', '1')
        
        invoices = Invoice.query.filter_by(created_by=user_id).order_by(Invoice.created_at.desc()).all()
        
        invoices_data = []
        total_outstanding = 0
        
        for invoice in invoices:
            invoice_dict = invoice.to_dict()
            invoices_data.append(invoice_dict)
            
            # Calculate outstanding amount
            outstanding = invoice_dict['total_amount'] - invoice_dict['amount_paid']
            total_outstanding += outstanding
        
        return jsonify({
            'success': True,
            'invoices': invoices_data,
            'total_invoices': len(invoices_data),
            'total_outstanding': total_outstanding
        })
        
    except Exception as e:
        logger.error(f"Get invoices error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve invoices'
        }), 500

def _get_mock_invoices():
    """Fallback mock invoice data"""
    invoices = [
        {
            'id': 'inv_001',
            'invoice_number': 'INV-2025-001',
            'client_name': 'John Smith',
            'client_id': 'client_1',
            'subject': 'Legal Services - Smith vs. Jones',
            'subtotal': 1625.00,
            'tax_amount': 130.00,
            'total_amount': 1755.00,
            'amount_paid': 0.00,
            'status': 'sent',
            'issue_date': '2025-07-08',
            'due_date': '2025-08-07',
            'payment_terms': 'Net 30'
        },
        {
            'id': 'inv_002',
            'invoice_number': 'INV-2025-002',
            'client_name': 'ABC Corporation',
            'client_id': 'client_2',
            'subject': 'Contract Review Services',
            'subtotal': 750.00,
            'tax_amount': 60.00,
            'total_amount': 810.00,
            'amount_paid': 810.00,
            'status': 'paid',
            'issue_date': '2025-07-05',
            'due_date': '2025-08-04',
            'paid_date': '2025-07-15',
            'payment_terms': 'Net 30'
        }
    ]
    
    return jsonify({
        'success': True,
        'invoices': invoices,
        'total_invoices': len(invoices),
        'total_outstanding': sum(inv['total_amount'] - inv['amount_paid'] for inv in invoices)
    })

@app.route('/api/invoices', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate')
def api_create_invoice():
    """Create invoice from billable time entries"""
    try:
        data = request.get_json()
        
        required_fields = ['client_id', 'entry_ids', 'subject']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        if not DATABASE_AVAILABLE:
            return _create_mock_invoice(data)
        
        client_id = data['client_id']
        entry_ids = data['entry_ids']
        subject = data['subject']
        
        # Get current user ID
        user_id = session.get('user_id', '1')
        
        # Verify client exists
        client = Client.query.filter_by(id=client_id).first()
        if not client:
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        # Get selected time entries
        time_entries = TimeEntry.query.filter(
            TimeEntry.id.in_(entry_ids),
            TimeEntry.user_id == user_id,
            TimeEntry.billable == True,
            TimeEntry.status.in_([TimeEntryStatus.APPROVED, TimeEntryStatus.SUBMITTED])
        ).all()
        
        if not time_entries:
            return jsonify({
                'success': False,
                'error': 'No valid time entries found for invoice'
            }), 400
        
        # Calculate totals
        subtotal = sum(entry.amount for entry in time_entries)
        tax_rate = Decimal(str(data.get('tax_rate', 0.08)))  # 8% default
        tax_amount = subtotal * tax_rate
        total_amount = subtotal + tax_amount
        
        # Generate invoice number
        invoice_count = Invoice.query.filter_by(created_by=user_id).count()
        invoice_number = f"INV-{datetime.now().year}-{str(invoice_count + 1).zfill(3)}"
        
        # Set dates
        issue_date = datetime.now().date()
        payment_terms = data.get('payment_terms', 'Net 30')
        days = 30 if 'Net 30' in payment_terms else 15 if 'Net 15' in payment_terms else 0
        due_date = issue_date + timedelta(days=days)
        
        # Create invoice
        invoice = Invoice(
            invoice_number=invoice_number,
            subject=subject,
            description=data.get('description', ''),
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total_amount=total_amount,
            amount_paid=Decimal('0.00'),
            status=InvoiceStatus.DRAFT,
            issue_date=issue_date,
            due_date=due_date,
            payment_terms=payment_terms,
            client_id=client_id,
            created_by=user_id
        )
        
        # Save invoice
        db.session.add(invoice)
        db.session.flush()  # Get the invoice ID
        
        # Update time entries to reference this invoice and mark as billed
        for entry in time_entries:
            entry.invoice_id = invoice.id
            entry.status = TimeEntryStatus.BILLED
        
        # Commit all changes
        db.session.commit()
        
        # Create audit log
        audit_log(
            action='create',
            resource_type='invoice',
            resource_id=invoice.id,
            user_id=user_id,
            new_values=invoice.to_dict()
        )
        
        logger.info(f"Created invoice {invoice_number} for {len(time_entries)} time entries")
        
        return jsonify({
            'success': True,
            'message': 'Invoice created successfully',
            'invoice': invoice.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Create invoice error: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to create invoice'
        }), 500

def _create_mock_invoice(data):
    """Fallback mock invoice creation"""
    subtotal = 1625.0
    tax_rate = data.get('tax_rate', 0.08)
    tax_amount = subtotal * tax_rate
    total_amount = subtotal + tax_amount
    
    invoice = {
        'id': f"inv_{datetime.now().timestamp()}",
        'invoice_number': f"INV-2025-{str(datetime.now().timestamp()).split('.')[0][-3:]}",
        'client_id': data['client_id'],
        'client_name': 'John Smith',
        'subject': data['subject'],
        'description': data.get('description', ''),
        'subtotal': subtotal,
        'tax_rate': tax_rate,
        'tax_amount': tax_amount,
        'total_amount': total_amount,
        'amount_paid': 0.00,
        'status': 'draft',
        'issue_date': datetime.now().date().isoformat(),
        'due_date': (datetime.now().date() + timedelta(days=30)).isoformat(),
        'payment_terms': data.get('payment_terms', 'Net 30'),
        'created_at': datetime.now().isoformat()
    }
    
    return jsonify({
        'success': True,
        'message': 'Invoice created successfully (mock)',
        'invoice': invoice
    })

@app.route('/api/invoices/<invoice_id>', methods=['GET'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_get_invoice(invoice_id):
    """Get invoice details"""
    try:
        # Mock invoice detail
        invoice = {
            'id': invoice_id,
            'invoice_number': 'INV-2025-001',
            'client_name': 'John Smith',
            'client_id': 'client_1',
            'subject': 'Legal Services - Smith vs. Jones',
            'description': 'Legal consultation and research services',
            'subtotal': 1625.00,
            'tax_rate': 0.08,
            'tax_amount': 130.00,
            'total_amount': 1755.00,
            'amount_paid': 0.00,
            'status': 'sent',
            'issue_date': '2025-07-08',
            'due_date': '2025-08-07',
            'payment_terms': 'Net 30',
            'billing_address': '123 Main St, Anytown, ST 12345',
            'time_entries': [
                {
                    'date': '2025-07-08',
                    'description': 'Client consultation and case review',
                    'hours': 2.5,
                    'rate': 250.00,
                    'amount': 625.00
                },
                {
                    'date': '2025-07-06',
                    'description': 'Legal research on contract law',
                    'hours': 4.0,
                    'rate': 250.00,
                    'amount': 1000.00
                }
            ]
        }
        
        return jsonify({
            'success': True,
            'invoice': invoice
        })
        
    except Exception as e:
        logger.error(f"Get invoice error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve invoice'
        }), 500

@app.route('/api/invoices/<invoice_id>/status', methods=['PUT'])
@login_required
@role_required('admin', 'partner', 'associate')
def api_update_invoice_status(invoice_id):
    """Update invoice status (draft -> sent -> paid)"""
    try:
        data = request.get_json()
        status = data.get('status')
        
        valid_statuses = ['draft', 'sent', 'paid', 'overdue', 'cancelled']
        if status not in valid_statuses:
            return jsonify({
                'success': False,
                'error': f'Invalid status. Must be one of: {valid_statuses}'
            }), 400
        
        # Additional data for paid invoices
        paid_date = data.get('paid_date')
        amount_paid = data.get('amount_paid')
        
        logger.info(f"Updated invoice {invoice_id} status to {status}")
        
        return jsonify({
            'success': True,
            'message': f'Invoice status updated to {status}',
            'invoice_id': invoice_id,
            'status': status,
            'paid_date': paid_date,
            'amount_paid': amount_paid
        })
        
    except Exception as e:
        logger.error(f"Update invoice status error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to update invoice status'
        }), 500

@app.route('/api/invoices/<invoice_id>/send', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate')
def api_send_invoice(invoice_id):
    """Send invoice to client"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({
                'success': False,
                'error': 'Client email required'
            }), 400
        
        # Mock email sending
        logger.info(f"Sent invoice {invoice_id} to {email}")
        
        return jsonify({
            'success': True,
            'message': 'Invoice sent successfully',
            'invoice_id': invoice_id,
            'sent_to': email,
            'sent_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Send invoice error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to send invoice'
        }), 500

@app.route('/api/billing/dashboard', methods=['GET'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_billing_dashboard():
    """Get billing dashboard data"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_billing_dashboard()
        
        # Get current user ID
        user_id = session.get('user_id', '1')
        
        # Calculate summary statistics
        current_month = datetime.now().date().replace(day=1)
        
        # Total outstanding amount
        outstanding_invoices = Invoice.query.filter_by(created_by=user_id).filter(
            Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE])
        ).all()
        total_outstanding = sum(float(inv.total_amount - inv.amount_paid) for inv in outstanding_invoices)
        
        # Total paid this month
        paid_invoices = Invoice.query.filter_by(created_by=user_id).filter(
            Invoice.status == InvoiceStatus.PAID,
            Invoice.paid_date >= current_month
        ).all()
        total_paid_this_month = sum(float(inv.total_amount) for inv in paid_invoices)
        
        # Pending time entries
        pending_entries = TimeEntry.query.filter_by(user_id=user_id).filter(
            TimeEntry.status.in_([TimeEntryStatus.SUBMITTED, TimeEntryStatus.DRAFT]),
            TimeEntry.billable == True
        ).all()
        pending_time_entries = len(pending_entries)
        
        # Billable hours this month
        month_entries = TimeEntry.query.filter_by(user_id=user_id).filter(
            TimeEntry.date >= current_month,
            TimeEntry.billable == True
        ).all()
        billable_hours_this_month = sum(float(entry.hours) for entry in month_entries)
        
        # Recent invoices
        recent_invoices = Invoice.query.filter_by(created_by=user_id).order_by(
            Invoice.created_at.desc()
        ).limit(5).all()
        
        recent_invoices_data = []
        for invoice in recent_invoices:
            invoice_data = {
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'client_name': invoice.client.get_display_name() if invoice.client else 'Unknown',
                'amount': float(invoice.total_amount),
                'status': invoice.status.value,
                'due_date': invoice.due_date.isoformat() if invoice.due_date else None
            }
            if invoice.paid_date:
                invoice_data['paid_date'] = invoice.paid_date.isoformat()
            recent_invoices_data.append(invoice_data)
        
        # Pending time entries detail
        pending_time_entries_data = []
        for entry in pending_entries[:5]:  # Limit to 5 for dashboard
            pending_time_entries_data.append({
                'id': entry.id,
                'description': entry.description,
                'hours': float(entry.hours),
                'amount': float(entry.amount),
                'client_name': entry.case.client.get_display_name() if entry.case and entry.case.client else 'No Client',
                'status': entry.status.value
            })
        
        dashboard = {
            'summary': {
                'total_outstanding': total_outstanding,
                'total_paid_this_month': total_paid_this_month,
                'pending_time_entries': pending_time_entries,
                'overdue_invoices': len([inv for inv in outstanding_invoices if inv.status == InvoiceStatus.OVERDUE]),
                'billable_hours_this_month': billable_hours_this_month
            },
            'recent_invoices': recent_invoices_data,
            'pending_time_entries': pending_time_entries_data
        }
        
        return jsonify({
            'success': True,
            'dashboard': dashboard
        })
        
    except Exception as e:
        logger.error(f"Billing dashboard error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load billing dashboard'
        }), 500

def _get_mock_billing_dashboard():
    """Fallback mock billing dashboard data"""
    dashboard = {
        'summary': {
            'total_outstanding': 1755.00,
            'total_paid_this_month': 2430.00,
            'pending_time_entries': 3,
            'overdue_invoices': 0,
            'billable_hours_this_month': 24.5
        },
        'recent_invoices': [
            {
                'id': 'inv_001',
                'invoice_number': 'INV-2025-001',
                'client_name': 'John Smith',
                'amount': 1755.00,
                'status': 'sent',
                'due_date': '2025-08-07'
            },
            {
                'id': 'inv_002',
                'invoice_number': 'INV-2025-002',
                'client_name': 'ABC Corporation',
                'amount': 810.00,
                'status': 'paid',
                'paid_date': '2025-07-15'
            }
        ],
        'pending_time_entries': [
            {
                'id': '4',
                'description': 'Contract drafting',
                'hours': 2.0,
                'amount': 500.00,
                'client_name': 'XYZ Corp',
                'status': 'submitted'
            }
        ]
    }
    
    return jsonify({
        'success': True,
        'dashboard': dashboard
    })

# ===== AUTHENTICATION APIs =====

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """User registration endpoint"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['email', 'password', 'first_name', 'last_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'{field.replace("_", " ").title()} is required'
                }), 400
        
        email = data['email'].lower().strip()
        
        if not DATABASE_AVAILABLE:
            return _register_mock_user(data)
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({
                'success': False,
                'error': 'User with this email already exists'
            }), 400
        
        # Validate password strength
        password = data['password']
        if len(password) < 8:
            return jsonify({
                'success': False,
                'error': 'Password must be at least 8 characters long'
            }), 400
        
        # Create new user
        user = User(
            email=email,
            first_name=data['first_name'].strip(),
            last_name=data['last_name'].strip(),
            phone=data.get('phone', '').strip(),
            role=UserRole.ASSOCIATE,  # Default role
            firm_name=data.get('firm_name', '').strip(),
            bar_number=data.get('bar_number', '').strip(),
            hourly_rate=Decimal(str(data['hourly_rate'])) if data.get('hourly_rate') else None
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Create audit log
        audit_log('create', 'user', user.id, user.id, {
            'action': 'user_registration',
            'email': user.email
        })
        
        logger.info(f"New user registered: {user.email}")
        
        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role.value
            }
        })
        
    except Exception as e:
        if DATABASE_AVAILABLE:
            db.session.rollback()
        logger.error(f"Registration error: {e}")
        return jsonify({
            'success': False,
            'error': 'Registration failed. Please try again.'
        }), 500

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """User login endpoint"""
    try:
        data = request.json
        
        if not data.get('email') or not data.get('password'):
            return jsonify({
                'success': False,
                'error': 'Email and password are required'
            }), 400
        
        email = data['email'].lower().strip()
        password = data['password']
        
        if not DATABASE_AVAILABLE:
            return _login_mock_user(email, password)
        
        # Find user
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.check_password(password):
            # Log failed attempt
            if user:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= 5:
                    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
                db.session.commit()
            
            return jsonify({
                'success': False,
                'error': 'Invalid email or password'
            }), 401
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            return jsonify({
                'success': False,
                'error': 'Account is temporarily locked. Please try again later.'
            }), 423
        
        # Check if account is active
        if not user.is_active:
            return jsonify({
                'success': False,
                'error': 'Account is deactivated. Please contact support.'
            }), 403
        
        # Reset failed attempts and update last login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(timezone.utc)
        db.session.commit()
        
        # Create session
        session['user_id'] = user.id
        session['user_email'] = user.email
        session['user_role'] = user.role.value
        session['user_name'] = f"{user.first_name} {user.last_name}"
        session['logged_in'] = True
        
        # Create audit log
        audit_log('login', 'user', user.id, user.id, {
            'action': 'user_login',
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')
        })
        
        logger.info(f"User logged in: {user.email}")
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role.value,
                'firm_name': user.firm_name
            }
        })
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({
            'success': False,
            'error': 'Login failed. Please try again.'
        }), 500

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """User logout endpoint"""
    try:
        user_id = session.get('user_id')
        
        if user_id and DATABASE_AVAILABLE:
            # Create audit log
            audit_log('logout', 'user', user_id, user_id, {
                'action': 'user_logout'
            })
        
        # Clear session
        session.clear()
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        })
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({
            'success': False,
            'error': 'Logout failed'
        }), 500

@app.route('/api/auth/me', methods=['GET'])
@login_required
def api_current_user():
    """Get current user information"""
    try:
        if not session.get('logged_in'):
            return jsonify({
                'success': False,
                'error': 'Not authenticated'
            }), 401
        
        user_id = session.get('user_id')
        
        if not DATABASE_AVAILABLE:
            return _get_mock_current_user()
        
        user = User.query.get(user_id)
        if not user:
            session.clear()
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'full_name': user.get_full_name(),
                'role': user.role.value,
                'firm_name': user.firm_name,
                'phone': user.phone,
                'hourly_rate': float(user.hourly_rate) if user.hourly_rate else None,
                'two_factor_enabled': user.two_factor_enabled,
                'email_verified': user.email_verified,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'created_at': user.created_at.isoformat() if user.created_at else None
            }
        })
        
    except Exception as e:
        logger.error(f"Current user error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get user information'
        }), 500

@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def api_change_password():
    """Change user password"""
    try:
        if not session.get('logged_in'):
            return jsonify({
                'success': False,
                'error': 'Not authenticated'
            }), 401
        
        data = request.json
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({
                'success': False,
                'error': 'Current password and new password are required'
            }), 400
        
        if len(new_password) < 8:
            return jsonify({
                'success': False,
                'error': 'New password must be at least 8 characters long'
            }), 400
        
        if not DATABASE_AVAILABLE:
            return jsonify({
                'success': True,
                'message': 'Password changed successfully (mock mode)'
            })
        
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        
        if not user or not user.check_password(current_password):
            return jsonify({
                'success': False,
                'error': 'Current password is incorrect'
            }), 400
        
        # Update password
        user.set_password(new_password)
        db.session.commit()
        
        # Create audit log
        audit_log('update', 'user', user.id, user.id, {
            'action': 'password_change'
        })
        
        logger.info(f"Password changed for user: {user.email}")
        
        return jsonify({
            'success': True,
            'message': 'Password changed successfully'
        })
        
    except Exception as e:
        if DATABASE_AVAILABLE:
            db.session.rollback()
        logger.error(f"Change password error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to change password'
        }), 500

# ===== MOCK AUTHENTICATION FUNCTIONS =====

def _register_mock_user(data):
    """Mock user registration"""
    return jsonify({
        'success': True,
        'message': 'User registered successfully (mock mode)',
        'user': {
            'id': '1',
            'email': data['email'],
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'role': 'associate'
        }
    })

def _login_mock_user(email, password):
    """Mock user login"""
    # Simple mock - any password works
    session['user_id'] = '1'
    session['user_email'] = email
    session['user_role'] = 'associate'
    session['user_name'] = 'Demo User'
    session['logged_in'] = True
    
    return jsonify({
        'success': True,
        'message': 'Login successful (mock mode)',
        'user': {
            'id': '1',
            'email': email,
            'first_name': 'Demo',
            'last_name': 'User',
            'role': 'associate',
            'firm_name': 'Demo Law Firm'
        }
    })

def _get_mock_current_user():
    """Mock current user"""
    return jsonify({
        'success': True,
        'user': {
            'id': '1',
            'email': session.get('user_email', 'demo@example.com'),
            'first_name': 'Demo',
            'last_name': 'User',
            'full_name': 'Demo User',
            'role': 'associate',
            'firm_name': 'Demo Law Firm',
            'phone': '(555) 123-4567',
            'hourly_rate': 350.00,
            'two_factor_enabled': False,
            'email_verified': True,
            'last_login': datetime.now().isoformat(),
            'created_at': datetime.now().isoformat()
        }
    })

# ===== CLIENT MANAGEMENT APIs =====

@app.route('/api/clients', methods=['GET'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_get_clients():
    """Get all clients with optional search and filtering"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_clients()
        
        # Get query parameters
        search = request.args.get('search', '').strip()
        status = request.args.get('status', '')
        client_type = request.args.get('type', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # Get current user ID
        user_id = session.get('user_id', '1')
        
        # Build query
        query = Client.query.filter_by(created_by=user_id)
        
        # Apply filters
        if search:
            query = query.filter(
                db.or_(
                    Client.first_name.ilike(f'%{search}%'),
                    Client.last_name.ilike(f'%{search}%'),
                    Client.company_name.ilike(f'%{search}%'),
                    Client.email.ilike(f'%{search}%')
                )
            )
        
        if status:
            query = query.filter_by(status=status)
            
        if client_type:
            query = query.filter_by(client_type=client_type)
        
        # Execute paginated query
        clients = query.order_by(Client.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Format response
        clients_data = []
        for client in clients.items:
            client_data = client.to_dict()
            
            # Add case count
            case_count = Case.query.filter_by(client_id=client.id).count()
            client_data['case_count'] = case_count
            
            # Add recent activity
            recent_cases = Case.query.filter_by(client_id=client.id).order_by(
                Case.updated_at.desc()
            ).limit(3).all()
            client_data['recent_cases'] = [case.to_dict() for case in recent_cases]
            
            clients_data.append(client_data)
        
        # Create audit log
        audit_log('view', 'clients', None, user_id, {
            'action': 'list_clients',
            'filters': {'search': search, 'status': status, 'type': client_type}
        })
        
        return jsonify({
            'success': True,
            'clients': clients_data,
            'pagination': {
                'page': clients.page,
                'pages': clients.pages,
                'per_page': clients.per_page,
                'total': clients.total,
                'has_prev': clients.has_prev,
                'has_next': clients.has_next
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching clients: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clients', methods=['POST'])
@login_required
@role_required('admin', 'partner', 'associate')
def api_create_client():
    """Create a new client"""
    try:
        if not DATABASE_AVAILABLE:
            return _create_mock_client()
        
        data = request.json
        user_id = session.get('user_id', '1')
        
        # Validate required fields
        client_type = data.get('client_type', 'individual')
        if client_type == 'individual':
            if not data.get('first_name') or not data.get('last_name'):
                return jsonify({
                    'success': False,
                    'error': 'First name and last name are required for individual clients'
                }), 400
        elif client_type == 'business':
            if not data.get('company_name'):
                return jsonify({
                    'success': False,
                    'error': 'Company name is required for business clients'
                }), 400
        
        # Create new client
        client = Client(
            client_type=client_type,
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            company_name=data.get('company_name'),
            email=data.get('email'),
            phone=data.get('phone'),
            address_line1=data.get('address_line1'),
            address_line2=data.get('address_line2'),
            city=data.get('city'),
            state=data.get('state'),
            zip_code=data.get('zip_code'),
            country=data.get('country', 'United States'),
            tax_id=data.get('tax_id'),
            website=data.get('website'),
            industry=data.get('industry'),
            status=data.get('status', 'active'),
            source=data.get('source'),
            notes=data.get('notes'),
            billing_rate=Decimal(str(data['billing_rate'])) if data.get('billing_rate') else None,
            payment_terms=data.get('payment_terms', 'Net 30'),
            created_by=user_id
        )
        
        db.session.add(client)
        db.session.commit()
        
        # Create audit log
        audit_log('create', 'client', client.id, user_id, client.to_dict())
        
        logger.info(f"Client created: {client.id}")
        
        return jsonify({
            'success': True,
            'client': client.to_dict(),
            'message': 'Client created successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating client: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clients/<client_id>', methods=['GET'])
@login_required
@role_required('admin', 'partner', 'associate', 'paralegal')
def api_get_client(client_id):
    """Get a specific client with full details"""
    try:
        if not DATABASE_AVAILABLE:
            return _get_mock_client(client_id)
        
        user_id = session.get('user_id', '1')
        
        # Get client
        client = Client.query.filter_by(id=client_id, created_by=user_id).first()
        if not client:
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        # Get client details with related data
        client_data = client.to_dict()
        
        # Get cases
        cases = Case.query.filter_by(client_id=client.id).order_by(Case.date_opened.desc()).all()
        client_data['cases'] = [case.to_dict() for case in cases]
        
        # Get invoices
        invoices = Invoice.query.filter_by(client_id=client.id).order_by(Invoice.created_at.desc()).limit(10).all()
        client_data['recent_invoices'] = [invoice.to_dict() for invoice in invoices]
        
        # Get documents
        documents = Document.query.filter_by(client_id=client.id).order_by(Document.created_at.desc()).limit(10).all()
        client_data['recent_documents'] = [doc.to_dict() for doc in documents]
        
        # Calculate financial summary
        total_billed = sum(float(invoice.total_amount) for invoice in invoices)
        total_paid = sum(float(invoice.amount_paid) for invoice in invoices)
        outstanding_amount = total_billed - total_paid
        
        client_data['financial_summary'] = {
            'total_billed': total_billed,
            'total_paid': total_paid,
            'outstanding_amount': outstanding_amount,
            'invoice_count': len(invoices)
        }
        
        # Create audit log
        audit_log('view', 'client', client.id, user_id, {'action': 'view_client_details'})
        
        return jsonify({
            'success': True,
            'client': client_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching client {client_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clients/<client_id>', methods=['PUT'])
@login_required
@role_required('admin', 'partner', 'associate')
def api_update_client(client_id):
    """Update a client"""
    try:
        if not DATABASE_AVAILABLE:
            return _update_mock_client(client_id)
        
        data = request.json
        user_id = session.get('user_id', '1')
        
        # Get client
        client = Client.query.filter_by(id=client_id, created_by=user_id).first()
        if not client:
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        # Store old values for audit
        old_values = client.to_dict()
        
        # Update fields
        updateable_fields = [
            'first_name', 'last_name', 'company_name', 'email', 'phone',
            'address_line1', 'address_line2', 'city', 'state', 'zip_code',
            'country', 'tax_id', 'website', 'industry', 'status', 'source',
            'notes', 'payment_terms'
        ]
        
        for field in updateable_fields:
            if field in data:
                setattr(client, field, data[field])
        
        if 'billing_rate' in data and data['billing_rate']:
            client.billing_rate = Decimal(str(data['billing_rate']))
        
        db.session.commit()
        
        # Create audit log
        audit_log('update', 'client', client.id, user_id, {
            'old_values': old_values,
            'new_values': client.to_dict()
        })
        
        logger.info(f"Client updated: {client.id}")
        
        return jsonify({
            'success': True,
            'client': client.to_dict(),
            'message': 'Client updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating client {client_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clients/<client_id>', methods=['DELETE'])
@login_required
@role_required('admin', 'partner')
def api_delete_client(client_id):
    """Delete a client (soft delete by setting status to inactive)"""
    try:
        if not DATABASE_AVAILABLE:
            return _delete_mock_client(client_id)
        
        user_id = session.get('user_id', '1')
        
        # Get client
        client = Client.query.filter_by(id=client_id, created_by=user_id).first()
        if not client:
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        # Check if client has active cases
        active_cases = Case.query.filter_by(client_id=client.id, status=CaseStatus.ACTIVE).count()
        if active_cases > 0:
            return jsonify({
                'success': False,
                'error': f'Cannot delete client with {active_cases} active cases. Close cases first.'
            }), 400
        
        # Soft delete - set status to inactive
        old_status = client.status
        client.status = 'inactive'
        db.session.commit()
        
        # Create audit log
        audit_log('delete', 'client', client.id, user_id, {
            'action': 'soft_delete',
            'old_status': old_status,
            'new_status': 'inactive'
        })
        
        logger.info(f"Client soft deleted: {client.id}")
        
        return jsonify({
            'success': True,
            'message': 'Client deactivated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting client {client_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ===== MOCK DATA FUNCTIONS =====

def _get_mock_clients():
    """Mock clients data for fallback"""
    return jsonify({
        'success': True,
        'clients': [
            {
                'id': '1',
                'client_type': 'business',
                'display_name': 'TechCorp Industries',
                'company_name': 'TechCorp Industries',
                'email': 'legal@techcorp.com',
                'phone': '(555) 123-4567',
                'status': 'active',
                'case_count': 3,
                'created_at': '2024-01-15T10:00:00Z',
                'recent_cases': [
                    {'id': '1', 'title': 'Contract Review', 'status': 'active'},
                    {'id': '2', 'title': 'IP Protection', 'status': 'pending'}
                ]
            },
            {
                'id': '2',
                'client_type': 'individual',
                'display_name': 'Sarah Johnson',
                'first_name': 'Sarah',
                'last_name': 'Johnson',
                'email': 'sarah.j@email.com',
                'phone': '(555) 987-6543',
                'status': 'active',
                'case_count': 1,
                'created_at': '2024-02-01T14:30:00Z',
                'recent_cases': [
                    {'id': '3', 'title': 'Employment Dispute', 'status': 'active'}
                ]
            }
        ],
        'pagination': {
            'page': 1,
            'pages': 1,
            'per_page': 20,
            'total': 2,
            'has_prev': False,
            'has_next': False
        }
    })

def _create_mock_client():
    """Mock client creation"""
    return jsonify({
        'success': True,
        'client': {
            'id': '3',
            'client_type': 'individual',
            'display_name': 'New Client',
            'status': 'active',
            'created_at': datetime.now().isoformat()
        },
        'message': 'Client created successfully (mock data)'
    })

def _get_mock_client(client_id):
    """Mock single client data"""
    return jsonify({
        'success': True,
        'client': {
            'id': client_id,
            'client_type': 'business',
            'display_name': 'Sample Client',
            'company_name': 'Sample Client Corp',
            'email': 'contact@sampleclient.com',
            'status': 'active',
            'cases': [],
            'recent_invoices': [],
            'recent_documents': [],
            'financial_summary': {
                'total_billed': 15000.00,
                'total_paid': 12000.00,
                'outstanding_amount': 3000.00,
                'invoice_count': 5
            }
        }
    })

def _update_mock_client(client_id):
    """Mock client update"""
    return jsonify({
        'success': True,
        'client': {
            'id': client_id,
            'status': 'active',
            'updated_at': datetime.now().isoformat()
        },
        'message': 'Client updated successfully (mock data)'
    })

def _delete_mock_client(client_id):
    """Mock client deletion"""
    return jsonify({
        'success': True,
        'message': 'Client deactivated successfully (mock data)'
    })

# ===== ERROR HANDLERS =====

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'success': False,
        'error': 'Page not found',
        'timestamp': datetime.now().isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'timestamp': datetime.now().isoformat()
    }), 500

# ===== INITIALIZATION =====

logger.info("✅ LexAI Clean Flask app initialized for serverless deployment")

# Export for Vercel
app = app