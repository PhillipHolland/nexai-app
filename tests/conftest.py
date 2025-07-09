"""
LexAI Testing Configuration and Fixtures
Production-ready testing infrastructure with comprehensive coverage
"""

import pytest
import tempfile
import os
import json
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import application components
from api.index import app as flask_app
from api.database_models import db, User, Client, Case, Document, Invoice

@pytest.fixture(scope='session')
def app():
    """Create and configure a new app instance for each test session."""
    # Create a temporary file for the test database
    db_fd, db_path = tempfile.mkstemp()
    
    flask_app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'DATABASE_URL': f'sqlite:///{db_path}',
        'SECRET_KEY': 'test-secret-key-for-testing-only',
        'UPLOAD_FOLDER': tempfile.mkdtemp(),
        'MAX_CONTENT_LENGTH': 16 * 1024 * 1024,  # 16MB max file size
        'BAGEL_AI_AVAILABLE': False,  # Mock AI services in tests
        'STRIPE_AVAILABLE': False,    # Mock payment services in tests
        'SPANISH_AVAILABLE': True,    # Enable Spanish testing
        'PRIVACY_AI_AVAILABLE': False # Mock privacy services in tests
    })
    
    # Create the database and the database table
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.drop_all()
    
    # Clean up
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()

@pytest.fixture
def auth_headers():
    """Headers for authenticated requests."""
    return {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer test-token'
    }

@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        'email': 'test@example.com',
        'first_name': 'Test',
        'last_name': 'User',
        'password': 'SecurePassword123!',
        'role': 'attorney',
        'phone': '+1234567890',
        'bar_number': 'CA12345'
    }

@pytest.fixture
def sample_client_data():
    """Sample client data for testing."""
    return {
        'first_name': 'John',
        'last_name': 'Doe',
        'email': 'john.doe@example.com',
        'phone': '+1987654321',
        'address': '123 Main St, City, State 12345',
        'company': 'Doe Enterprises',
        'client_type': 'individual'
    }

@pytest.fixture
def sample_case_data():
    """Sample case data for testing."""
    return {
        'title': 'Contract Dispute Case',
        'description': 'Complex commercial contract dispute',
        'practice_area': 'contract',
        'status': 'active',
        'priority': 'high',
        'estimated_hours': 50,
        'hourly_rate': 350.00
    }

@pytest.fixture
def sample_document_data():
    """Sample document data for testing."""
    return {
        'title': 'Test Contract',
        'description': 'A test contract document',
        'document_type': 'contract',
        'content': 'This is a test contract content...',
        'file_size': 1024,
        'file_type': 'application/pdf'
    }

@pytest.fixture
def sample_invoice_data():
    """Sample invoice data for testing."""
    return {
        'invoice_number': 'INV-2024-001',
        'description': 'Legal services rendered',
        'amount': 1750.00,
        'tax_amount': 157.50,
        'total_amount': 1907.50,
        'due_date': datetime.now() + timedelta(days=30),
        'status': 'pending'
    }

@pytest.fixture
def mock_bagel_service():
    """Mock Bagel RL service for testing."""
    with patch('api.bagel_service.query_bagel_legal_ai') as mock_bagel:
        mock_bagel.return_value = {
            'success': True,
            'response': 'Mock AI analysis response',
            'confidence_score': 0.85,
            'processing_time': 1.2
        }
        yield mock_bagel

@pytest.fixture
def mock_spanish_service():
    """Mock Spanish translation service for testing."""
    with patch('api.spanish_service.translate_legal_text') as mock_translate:
        mock_translate.return_value = {
            'success': True,
            'original_text': 'Contract',
            'translated_text': 'Contrato',
            'source_language': 'en',
            'target_language': 'es',
            'confidence_score': 0.9,
            'legal_context': 'contract',
            'warnings': [],
            'bagel_enhanced': True
        }
        yield mock_translate

@pytest.fixture
def mock_document_analysis():
    """Mock document analysis service for testing."""
    with patch('api.document_ai_service.analyze_document_comprehensive') as mock_analysis:
        mock_analysis.return_value = {
            'success': True,
            'document_id': 'test-doc-123',
            'classification': 'contract',
            'extracted_text': 'Sample contract text...',
            'key_terms': ['party', 'agreement', 'terms'],
            'pii_detected': False,
            'confidence_score': 0.88,
            'processing_time': 2.1,
            'bagel_insights': {
                'success': True,
                'analysis': 'Mock contract analysis'
            }
        }
        yield mock_analysis

@pytest.fixture
def mock_legal_research():
    """Mock legal research service for testing."""
    with patch('api.legal_research_service.comprehensive_legal_research') as mock_research:
        mock_research.return_value = {
            'success': True,
            'query': 'contract law',
            'results': {
                'sources': {
                    'case_law': [
                        {
                            'title': 'Sample v. Case',
                            'citation': '123 F.3d 456 (9th Cir. 2020)',
                            'summary': 'Mock case summary',
                            'relevance_score': 85
                        }
                    ],
                    'statutes': [],
                    'secondary_sources': []
                }
            },
            'total_results': 1,
            'processing_time': 1.8
        }
        yield mock_research

@pytest.fixture
def mock_contract_analysis():
    """Mock contract analysis service for testing."""
    with patch('api.contract_analysis_service.analyze_contract_comprehensive') as mock_contract:
        mock_contract.return_value = {
            'success': True,
            'contract_id': 'contract-123',
            'contract_type': 'service',
            'overall_risk_score': 35.0,
            'key_terms': {
                'parties': ['Company A', 'Company B'],
                'governing_law': 'California'
            },
            'clauses': [],
            'missing_clauses': [],
            'red_flags': [],
            'recommendations': ['Review with legal counsel'],
            'compliance_issues': [],
            'financial_terms': {'total_value': 50000.0},
            'timeline_analysis': {},
            'bagel_insights': {
                'success': True,
                'strategic_analysis': 'Mock strategic analysis'
            }
        }
        yield mock_contract

@pytest.fixture
def authenticated_user(app, sample_user_data):
    """Create and return an authenticated user."""
    with app.app_context():
        user = User(
            email=sample_user_data['email'],
            first_name=sample_user_data['first_name'],
            last_name=sample_user_data['last_name'],
            role=sample_user_data['role'],
            phone=sample_user_data['phone'],
            bar_number=sample_user_data['bar_number'],
            is_verified=True,
            totp_secret='test-secret'
        )
        user.set_password(sample_user_data['password'])
        db.session.add(user)
        db.session.commit()
        return user

@pytest.fixture
def sample_client(app, authenticated_user, sample_client_data):
    """Create and return a sample client."""
    with app.app_context():
        client = Client(
            first_name=sample_client_data['first_name'],
            last_name=sample_client_data['last_name'],
            email=sample_client_data['email'],
            phone=sample_client_data['phone'],
            address=sample_client_data['address'],
            company=sample_client_data['company'],
            client_type=sample_client_data['client_type'],
            attorney_id=authenticated_user.id
        )
        db.session.add(client)
        db.session.commit()
        return client

@pytest.fixture
def sample_case(app, sample_client, sample_case_data):
    """Create and return a sample case."""
    with app.app_context():
        case = Case(
            title=sample_case_data['title'],
            description=sample_case_data['description'],
            practice_area=sample_case_data['practice_area'],
            status=sample_case_data['status'],
            priority=sample_case_data['priority'],
            estimated_hours=sample_case_data['estimated_hours'],
            hourly_rate=sample_case_data['hourly_rate'],
            client_id=sample_client.id
        )
        db.session.add(case)
        db.session.commit()
        return case

@pytest.fixture
def test_file():
    """Create a temporary test file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write('This is a test document content for LexAI testing.')
        f.flush()
        yield f.name
    os.unlink(f.name)

@pytest.fixture
def mock_stripe_payment():
    """Mock Stripe payment processing."""
    with patch('stripe.PaymentIntent.create') as mock_payment:
        mock_payment.return_value = Mock(
            id='pi_test_123',
            status='succeeded',
            amount=5000,
            currency='usd'
        )
        yield mock_payment

@pytest.fixture
def performance_monitor():
    """Monitor performance during tests."""
    import time
    import psutil
    import os
    
    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.start_memory = None
            self.process = psutil.Process(os.getpid())
        
        def start_monitoring(self):
            self.start_time = time.time()
            self.start_memory = self.process.memory_info().rss
        
        def stop_monitoring(self):
            end_time = time.time()
            end_memory = self.process.memory_info().rss
            
            return {
                'execution_time': end_time - self.start_time,
                'memory_used': end_memory - self.start_memory,
                'cpu_percent': self.process.cpu_percent()
            }
    
    return PerformanceMonitor()

@pytest.fixture
def security_headers():
    """Security headers for testing."""
    return {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'"
    }

# Test database helpers
def create_test_user(email="test@example.com", role="attorney"):
    """Helper function to create test users."""
    user = User(
        email=email,
        first_name="Test",
        last_name="User",
        role=role,
        is_verified=True
    )
    user.set_password("TestPassword123!")
    return user

def create_test_client(user_id, name="Test Client"):
    """Helper function to create test clients."""
    return Client(
        first_name=name.split()[0],
        last_name=name.split()[1] if len(name.split()) > 1 else "Client",
        email=f"{name.lower().replace(' ', '.')}@example.com",
        attorney_id=user_id
    )

def create_test_case(client_id, title="Test Case"):
    """Helper function to create test cases."""
    return Case(
        title=title,
        description="Test case description",
        practice_area="general",
        status="active",
        client_id=client_id
    )

# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "security: marks tests as security tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
    config.addinivalue_line(
        "markers", "api: marks tests as API tests"
    )
    config.addinivalue_line(
        "markers", "ui: marks tests as UI tests"
    )

def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add markers based on file location
        if "test_security" in item.nodeid:
            item.add_marker(pytest.mark.security)
        elif "test_performance" in item.nodeid:
            item.add_marker(pytest.mark.performance)
        elif "test_api" in item.nodeid:
            item.add_marker(pytest.mark.api)
        elif "test_integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # Mark slow tests
        if any(keyword in item.nodeid for keyword in ["slow", "performance", "load"]):
            item.add_marker(pytest.mark.slow)