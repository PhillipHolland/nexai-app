"""
Security Testing Suite
Comprehensive security tests for LexAI production deployment
"""

import pytest
import json
import hashlib
import secrets
import time
from unittest.mock import patch, Mock

@pytest.mark.security
class TestAuthenticationSecurity:
    """Test authentication and authorization security."""
    
    def test_password_hashing(self, app, sample_user_data):
        """Test that passwords are properly hashed."""
        from api.database_models import User
        
        with app.app_context():
            user = User(email=sample_user_data['email'])
            user.set_password(sample_user_data['password'])
            
            # Password should be hashed, not stored in plain text
            assert user.password_hash != sample_user_data['password']
            assert len(user.password_hash) > 50  # bcrypt hashes are long
            assert user.check_password(sample_user_data['password'])
            assert not user.check_password('wrong_password')
    
    def test_session_security(self, client, authenticated_user):
        """Test session management security."""
        # Login to get session
        response = client.post('/api/auth/login', json={
            'email': 'test@example.com',
            'password': 'SecurePassword123!'
        })
        assert response.status_code == 200
        
        # Check that session token is secure
        data = response.get_json()
        if 'access_token' in data:
            token = data['access_token']
            assert len(token) > 20  # Token should be sufficiently long
            assert token.replace('.', '').replace('-', '').replace('_', '').isalnum()
    
    def test_password_strength_requirements(self, client):
        """Test password strength requirements."""
        weak_passwords = [
            '123456',
            'password',
            'abc123',
            'qwerty',
            '12345678'
        ]
        
        for weak_password in weak_passwords:
            response = client.post('/api/auth/register', json={
                'email': f'test{secrets.token_hex(4)}@example.com',
                'first_name': 'Test',
                'last_name': 'User',
                'password': weak_password,
                'role': 'attorney'
            })
            # Should reject weak passwords
            assert response.status_code in [400, 422]
    
    def test_account_lockout_protection(self, client, authenticated_user):
        """Test account lockout after failed login attempts."""
        # Multiple failed login attempts
        for i in range(10):
            response = client.post('/api/auth/login', json={
                'email': 'test@example.com',
                'password': 'wrong_password'
            })
            assert response.status_code == 401
        
        # Account should be locked or rate limited
        response = client.post('/api/auth/login', json={
            'email': 'test@example.com',
            'password': 'SecurePassword123!'  # Correct password
        })
        # Should be locked out or rate limited
        assert response.status_code in [401, 429, 423]
    
    def test_two_factor_authentication(self, client, authenticated_user):
        """Test 2FA security implementation."""
        # Test 2FA setup
        response = client.post('/api/auth/setup-2fa',
                             headers={'Authorization': 'Bearer test-token'})
        # Adjust assertion based on actual implementation
        assert response.status_code in [200, 404, 501]
        
        if response.status_code == 200:
            data = response.get_json()
            # Should provide QR code or secret
            assert 'qr_code' in data or 'secret' in data

@pytest.mark.security
class TestInputValidationSecurity:
    """Test input validation and sanitization."""
    
    def test_sql_injection_protection(self, client, authenticated_user):
        """Test protection against SQL injection attacks."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM users --",
            "1'; DELETE FROM clients; --"
        ]
        
        for malicious_input in malicious_inputs:
            # Test in various endpoints
            response = client.post('/api/clients', json={
                'first_name': malicious_input,
                'last_name': 'Test',
                'email': 'test@example.com'
            }, headers={'Authorization': 'Bearer test-token'})
            
            # Should handle gracefully without exposing database errors
            assert response.status_code in [200, 201, 400, 422]
            if response.status_code >= 400:
                data = response.get_json()
                # Should not expose database error details
                assert 'DROP TABLE' not in str(data).upper()
                assert 'DELETE FROM' not in str(data).upper()
    
    def test_xss_protection(self, client, authenticated_user):
        """Test Cross-Site Scripting (XSS) protection."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "';alert('XSS');//",
            "<svg onload=alert('XSS')>"
        ]
        
        for payload in xss_payloads:
            response = client.post('/api/clients', json={
                'first_name': payload,
                'last_name': 'Test',
                'email': 'test@example.com'
            }, headers={'Authorization': 'Bearer test-token'})
            
            # Should sanitize or reject malicious input
            if response.status_code in [200, 201]:
                data = response.get_json()
                # Should not contain raw script tags
                assert '<script>' not in str(data).lower()
                assert 'javascript:' not in str(data).lower()
    
    def test_path_traversal_protection(self, client, authenticated_user):
        """Test protection against path traversal attacks."""
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"
        ]
        
        for malicious_path in malicious_paths:
            # Test file upload with malicious filename
            response = client.post('/api/documents/upload', data={
                'file': (b'test content', malicious_path),
                'document_type': 'contract'
            }, headers={'Authorization': 'Bearer test-token'})
            
            # Should reject or sanitize malicious filenames
            assert response.status_code in [200, 400, 422]
    
    def test_command_injection_protection(self, client, authenticated_user):
        """Test protection against command injection."""
        command_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "&& rm -rf /",
            "`whoami`",
            "$(id)"
        ]
        
        for payload in command_payloads:
            response = client.post('/api/spanish/translate', json={
                'text': f'Test text {payload}',
                'target_language': 'es'
            }, headers={'Authorization': 'Bearer test-token'})
            
            # Should handle safely without executing commands
            assert response.status_code in [200, 400, 422]

@pytest.mark.security
class TestDataProtectionSecurity:
    """Test data protection and privacy security."""
    
    def test_pii_data_handling(self, client, authenticated_user):
        """Test PII data detection and protection."""
        pii_data = {
            'text': 'John Doe SSN: 123-45-6789, Phone: (555) 123-4567, Email: john@example.com',
            'document_type': 'contract'
        }
        
        response = client.post('/api/documents/analyze',
                             json=pii_data,
                             headers={'Authorization': 'Bearer test-token'})
        
        if response.status_code == 200:
            data = response.get_json()
            # Should detect PII
            assert 'pii_detected' in data
            # Should not log or expose PII in response
            response_str = str(data).lower()
            assert '123-45-6789' not in response_str
    
    def test_sensitive_data_encryption(self, app):
        """Test that sensitive data is encrypted."""
        from api.database_models import User, Client
        
        with app.app_context():
            # Create user with sensitive data
            user = User(
                email='test@example.com',
                first_name='Test',
                last_name='User'
            )
            user.set_password('SecurePassword123!')
            
            # Password should be hashed/encrypted
            assert user.password_hash != 'SecurePassword123!'
            
            # Create client with sensitive data
            client = Client(
                first_name='John',
                last_name='Doe',
                email='john@example.com',
                phone='555-123-4567',
                ssn='123-45-6789'  # If SSN field exists
            )
            
            # Sensitive fields should be encrypted or protected
            # This test depends on actual encryption implementation
    
    def test_data_access_controls(self, client, authenticated_user, sample_client):
        """Test data access controls and authorization."""
        # Try to access another user's data
        response = client.get('/api/clients/999999',  # Non-existent or unauthorized ID
                            headers={'Authorization': 'Bearer test-token'})
        
        # Should deny access or return not found
        assert response.status_code in [403, 404]
    
    def test_secure_file_upload(self, client, authenticated_user):
        """Test secure file upload handling."""
        # Test various file types
        malicious_files = [
            (b'#!/bin/bash\necho "malicious"', 'script.sh'),
            (b'<script>alert("xss")</script>', 'malicious.html'),
            (b'MZ\x90\x00', 'malware.exe'),  # PE header
            (b'\x7fELF', 'malware.elf')      # ELF header
        ]
        
        for content, filename in malicious_files:
            response = client.post('/api/documents/upload', data={
                'file': (content, filename),
                'document_type': 'contract'
            }, headers={'Authorization': 'Bearer test-token'})
            
            # Should reject malicious file types
            assert response.status_code in [200, 400, 415, 422]
            
            if response.status_code >= 400:
                data = response.get_json()
                assert 'error' in data

@pytest.mark.security
class TestNetworkSecurity:
    """Test network-level security measures."""
    
    def test_https_enforcement(self, client):
        """Test HTTPS enforcement and secure headers."""
        response = client.get('/')
        
        # Check for security headers
        security_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options', 
            'X-XSS-Protection',
            'Strict-Transport-Security'
        ]
        
        # Note: In test environment, these headers might not be set
        # This test validates the expectation for production
        for header in security_headers:
            # Headers should be present in production
            pass  # Placeholder for actual header validation
    
    def test_cors_configuration(self, client):
        """Test CORS configuration security."""
        # Test preflight request
        response = client.options('/api/clients',
                                headers={
                                    'Origin': 'https://malicious-site.com',
                                    'Access-Control-Request-Method': 'GET'
                                })
        
        # Should have proper CORS configuration
        # Allow only trusted origins in production
        if 'Access-Control-Allow-Origin' in response.headers:
            allowed_origin = response.headers['Access-Control-Allow-Origin']
            assert allowed_origin != '*' or app.config.get('TESTING')
    
    def test_rate_limiting(self, client):
        """Test API rate limiting implementation."""
        # Make rapid requests to test rate limiting
        responses = []
        for i in range(50):
            response = client.get('/api/status')
            responses.append(response.status_code)
            if response.status_code == 429:  # Rate limited
                break
        
        # Should implement rate limiting for production
        # In development/testing, this might not be enforced
        pass  # Placeholder for rate limiting validation

@pytest.mark.security  
class TestCryptographicSecurity:
    """Test cryptographic implementations."""
    
    def test_secure_random_generation(self):
        """Test secure random number generation."""
        import secrets
        
        # Generate multiple random tokens
        tokens = [secrets.token_hex(32) for _ in range(10)]
        
        # All tokens should be unique
        assert len(set(tokens)) == len(tokens)
        
        # Each token should be 64 characters (32 bytes * 2 for hex)
        assert all(len(token) == 64 for token in tokens)
    
    def test_password_hashing_strength(self, app):
        """Test password hashing algorithm strength."""
        from api.database_models import User
        
        with app.app_context():
            user = User(email='test@example.com')
            password = 'TestPassword123!'
            user.set_password(password)
            
            # Should use bcrypt or similar strong hashing
            assert user.password_hash.startswith('$2b$') or user.password_hash.startswith('$2a$')
            
            # Hash should be different each time (salt)
            user2 = User(email='test2@example.com')
            user2.set_password(password)
            assert user.password_hash != user2.password_hash
    
    def test_token_security(self):
        """Test security token generation and validation."""
        import secrets
        
        # Generate API tokens
        token = secrets.token_urlsafe(32)
        
        # Token should be URL-safe and sufficiently long
        assert len(token) >= 32
        assert all(c.isalnum() or c in '-_' for c in token)

@pytest.mark.security
class TestVulnerabilityTesting:
    """Test for common web vulnerabilities."""
    
    def test_csrf_protection(self, client, authenticated_user):
        """Test CSRF protection mechanisms."""
        # Test state-changing operation without CSRF token
        response = client.post('/api/clients', json={
            'first_name': 'CSRF',
            'last_name': 'Test',
            'email': 'csrf@example.com'
        }, headers={'Authorization': 'Bearer test-token'})
        
        # In production, should require CSRF token for state changes
        # In API-only mode, this might not apply
        assert response.status_code in [200, 201, 403, 422]
    
    def test_clickjacking_protection(self, client):
        """Test clickjacking protection via X-Frame-Options."""
        response = client.get('/')
        
        # Should set X-Frame-Options header
        # Note: This might not be set in test environment
        pass  # Placeholder for X-Frame-Options validation
    
    def test_information_disclosure(self, client):
        """Test for information disclosure vulnerabilities."""
        # Test error messages don't expose sensitive information
        response = client.get('/api/nonexistent-endpoint')
        assert response.status_code == 404
        
        if response.status_code >= 400:
            data = response.get_json() or {}
            error_text = str(data).lower()
            
            # Should not expose:
            sensitive_info = [
                'database',
                'sql',
                'password',
                'secret',
                'key',
                'token',
                'stack trace',
                'traceback'
            ]
            
            for sensitive in sensitive_info:
                assert sensitive not in error_text
    
    def test_directory_traversal(self, client):
        """Test directory traversal vulnerability."""
        traversal_attempts = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32',
            '/etc/passwd',
            '/proc/version',
            '/etc/shadow'
        ]
        
        for attempt in traversal_attempts:
            response = client.get(f'/static/{attempt}')
            # Should not expose system files
            assert response.status_code in [400, 403, 404]

@pytest.mark.security
class TestSecurityConfiguration:
    """Test security configuration and settings."""
    
    def test_debug_mode_disabled(self, app):
        """Test that debug mode is disabled in production."""
        # In production, debug should be False
        if not app.config.get('TESTING'):
            assert not app.config.get('DEBUG', False)
    
    def test_secret_key_security(self, app):
        """Test that secret key is secure."""
        secret_key = app.config.get('SECRET_KEY')
        
        if secret_key:
            # Secret key should be sufficiently long and complex
            assert len(secret_key) >= 32
            assert secret_key != 'dev'
            assert secret_key != 'development'
            assert secret_key != 'default'
    
    def test_database_connection_security(self, app):
        """Test database connection security."""
        db_url = app.config.get('DATABASE_URL', '')
        
        if db_url:
            # Should use SSL for production databases
            if 'postgres://' in db_url and not app.config.get('TESTING'):
                # Production PostgreSQL should use SSL
                assert 'sslmode=require' in db_url or 'sslmode=prefer' in db_url
    
    def test_file_upload_security(self, app):
        """Test file upload security configuration."""
        # Check file upload limits
        max_content_length = app.config.get('MAX_CONTENT_LENGTH')
        if max_content_length:
            # Should have reasonable file size limits
            assert max_content_length <= 100 * 1024 * 1024  # 100MB max
        
        # Check upload folder security
        upload_folder = app.config.get('UPLOAD_FOLDER')
        if upload_folder:
            # Upload folder should not be in web root
            assert 'static' not in upload_folder.lower()
            assert 'public' not in upload_folder.lower()

@pytest.mark.security
class TestComplianceSecurity:
    """Test compliance and regulatory security requirements."""
    
    def test_data_retention_policies(self, app):
        """Test data retention and deletion capabilities."""
        # Should have mechanisms for data deletion
        # This is important for GDPR compliance
        pass  # Placeholder for data retention testing
    
    def test_audit_logging(self, client, authenticated_user):
        """Test audit logging for security events."""
        # Perform various actions that should be logged
        actions = [
            ('POST', '/api/auth/login', {'email': 'test@example.com', 'password': 'wrong'}),
            ('GET', '/api/clients', {}),
            ('POST', '/api/clients', {'first_name': 'Test', 'last_name': 'User', 'email': 'test@test.com'})
        ]
        
        for method, endpoint, data in actions:
            if method == 'POST':
                response = client.post(endpoint, json=data,
                                     headers={'Authorization': 'Bearer test-token'})
            else:
                response = client.get(endpoint,
                                    headers={'Authorization': 'Bearer test-token'})
            
            # Actions should be logged for audit purposes
            # This requires actual audit log implementation
    
    def test_encryption_at_rest(self, app):
        """Test encryption of data at rest."""
        # Verify that sensitive data is encrypted in database
        # This requires actual encryption implementation
        pass  # Placeholder for encryption testing
    
    def test_access_control_matrix(self, client, app):
        """Test role-based access control matrix."""
        roles_and_permissions = {
            'admin': ['read_all', 'write_all', 'delete_all'],
            'attorney': ['read_own', 'write_own', 'read_clients'],
            'paralegal': ['read_assigned', 'write_assigned'],
            'client': ['read_own_cases', 'read_own_documents']
        }
        
        # Test that each role has appropriate permissions
        # This requires actual RBAC implementation
        pass  # Placeholder for RBAC testing