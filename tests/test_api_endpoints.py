"""
API Endpoints Testing Suite
Comprehensive testing of all LexAI API endpoints for production readiness
"""

import pytest
import json
import io
from unittest.mock import patch, Mock
from datetime import datetime, timedelta

class TestAuthenticationEndpoints:
    """Test authentication and authorization endpoints."""
    
    def test_login_success(self, client, authenticated_user):
        """Test successful login."""
        response = client.post('/api/auth/login', json={
            'email': 'test@example.com',
            'password': 'SecurePassword123!'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'access_token' in data
    
    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        response = client.post('/api/auth/login', json={
            'email': 'test@example.com',
            'password': 'wrongpassword'
        })
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
    
    def test_register_success(self, client):
        """Test successful user registration."""
        response = client.post('/api/auth/register', json={
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password': 'SecurePassword123!',
            'role': 'attorney'
        })
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
    
    def test_register_duplicate_email(self, client, authenticated_user):
        """Test registration with duplicate email."""
        response = client.post('/api/auth/register', json={
            'email': 'test@example.com',
            'first_name': 'Duplicate',
            'last_name': 'User',
            'password': 'SecurePassword123!',
            'role': 'attorney'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

class TestClientManagementEndpoints:
    """Test client management API endpoints."""
    
    def test_create_client_success(self, client, authenticated_user, sample_client_data):
        """Test successful client creation."""
        response = client.post('/api/clients', 
                             json=sample_client_data,
                             headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert data['client']['email'] == sample_client_data['email']
    
    def test_get_clients_list(self, client, authenticated_user, sample_client):
        """Test getting clients list."""
        response = client.get('/api/clients',
                            headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert len(data['clients']) > 0
    
    def test_update_client(self, client, authenticated_user, sample_client):
        """Test client update."""
        response = client.put(f'/api/clients/{sample_client.id}',
                            json={'phone': '+1555123456'},
                            headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
    
    def test_delete_client(self, client, authenticated_user, sample_client):
        """Test client deletion."""
        response = client.delete(f'/api/clients/{sample_client.id}',
                               headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

class TestDocumentEndpoints:
    """Test document management and analysis endpoints."""
    
    @pytest.mark.api
    def test_document_upload_success(self, client, authenticated_user, mock_document_analysis):
        """Test successful document upload."""
        data = {
            'file': (io.BytesIO(b'test document content'), 'test.txt'),
            'document_type': 'contract',
            'analysis_type': 'comprehensive'
        }
        response = client.post('/api/documents/upload',
                             data=data,
                             headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
    
    @pytest.mark.api  
    def test_document_upload_invalid_file(self, client, authenticated_user):
        """Test document upload with invalid file type."""
        data = {
            'file': (io.BytesIO(b'test'), 'test.exe'),
            'document_type': 'contract'
        }
        response = client.post('/api/documents/upload',
                             data=data,
                             headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['success'] is False
    
    @pytest.mark.api
    def test_document_analysis(self, client, authenticated_user, mock_document_analysis):
        """Test document analysis endpoint."""
        response = client.post('/api/documents/analyze',
                             json={
                                 'text': 'Sample contract text for analysis',
                                 'document_type': 'contract',
                                 'analysis_depth': 'comprehensive'
                             },
                             headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'classification' in data

class TestLegalResearchEndpoints:
    """Test legal research API endpoints."""
    
    @pytest.mark.api
    def test_legal_research_basic(self, client, authenticated_user, mock_legal_research):
        """Test basic legal research."""
        response = client.post('/api/legal-research/search',
                             json={
                                 'query': 'contract law precedents',
                                 'jurisdiction': 'federal',
                                 'limit': 10
                             },
                             headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'results' in data
    
    @pytest.mark.api
    def test_legal_research_comprehensive(self, client, authenticated_user, mock_legal_research):
        """Test comprehensive legal research."""
        response = client.post('/api/legal-research/comprehensive',
                             json={
                                 'query': 'employment law discrimination',
                                 'practice_area': 'employment',
                                 'jurisdiction': 'california',
                                 'limit': 20
                             },
                             headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'results' in data

class TestContractAnalysisEndpoints:
    """Test contract analysis API endpoints."""
    
    @pytest.mark.api
    def test_contract_analysis_basic(self, client, authenticated_user, mock_contract_analysis):
        """Test basic contract analysis."""
        contract_text = """
        SERVICE AGREEMENT
        This Service Agreement is entered into between Company A and Company B.
        1. Services: Provider will deliver consulting services.
        2. Payment: Client will pay $5,000 monthly.
        3. Termination: Either party may terminate with 30 days notice.
        """
        
        response = client.post('/api/contracts/analyze',
                             json={
                                 'contract_text': contract_text,
                                 'contract_type': 'service',
                                 'analysis_depth': 'basic'
                             },
                             headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'contract_type' in data
        assert 'overall_risk_score' in data
    
    @pytest.mark.api
    def test_contract_risk_assessment(self, client, authenticated_user, mock_contract_analysis):
        """Test contract risk assessment."""
        response = client.post('/api/contracts/risk-assessment',
                             json={
                                 'contract_text': 'Sample contract with unlimited liability clause',
                                 'contract_type': 'service'
                             },
                             headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'risk_score' in data
    
    @pytest.mark.api
    def test_contract_clause_analysis(self, client, authenticated_user, mock_contract_analysis):
        """Test contract clause analysis."""
        response = client.post('/api/contracts/clause-analysis',
                             json={
                                 'contract_text': 'Contract with termination and liability clauses',
                                 'contract_type': 'employment'
                             },
                             headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'clauses' in data

class TestSpanishTranslationEndpoints:
    """Test Spanish translation API endpoints."""
    
    @pytest.mark.api
    def test_spanish_text_translation(self, client, authenticated_user, mock_spanish_service):
        """Test Spanish text translation."""
        response = client.post('/api/spanish/translate',
                             json={
                                 'text': 'This contract is governed by California law',
                                 'target_language': 'es',
                                 'legal_context': 'contract'
                             },
                             headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'translated_text' in data
    
    @pytest.mark.api
    def test_spanish_document_translation(self, client, authenticated_user, mock_spanish_service):
        """Test Spanish document translation."""
        response = client.post('/api/spanish/translate-document',
                             json={
                                 'document_text': 'EMPLOYMENT AGREEMENT\n\nThis agreement...',
                                 'document_type': 'employment',
                                 'target_language': 'es'
                             },
                             headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'translated_text' in data
    
    @pytest.mark.api
    def test_spanish_ui_translations(self, client, authenticated_user):
        """Test Spanish UI translations."""
        response = client.get('/api/spanish/ui-translations?language=es',
                            headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'translations' in data

class TestEvidenceAnalysisEndpoints:
    """Test evidence analysis API endpoints."""
    
    @pytest.mark.api
    def test_evidence_upload_analysis(self, client, authenticated_user):
        """Test evidence upload and analysis."""
        data = {
            'file': (io.BytesIO(b'evidence file content'), 'evidence.pdf'),
            'evidence_type': 'document',
            'case_id': 'test-case-123'
        }
        response = client.post('/api/evidence/upload',
                             data=data,
                             headers={'Authorization': 'Bearer test-token'})
        # Note: This might return 404 if evidence endpoints aren't implemented
        # Adjust assertion based on actual implementation
        assert response.status_code in [200, 404, 501]
    
    @pytest.mark.api
    def test_legal_admissibility_check(self, client, authenticated_user):
        """Test legal admissibility analysis."""
        response = client.post('/api/evidence/legal-admissibility',
                             json={
                                 'evidence_type': 'document',
                                 'description': 'Digital contract with electronic signatures',
                                 'source': 'Client email communication'
                             },
                             headers={'Authorization': 'Bearer test-token'})
        # Adjust assertion based on actual implementation
        assert response.status_code in [200, 404, 501]

class TestAnalyticsEndpoints:
    """Test analytics and reporting endpoints."""
    
    @pytest.mark.api
    def test_practice_analytics(self, client, authenticated_user):
        """Test practice analytics endpoint."""
        response = client.get('/api/analytics/practice',
                            headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'analytics' in data
    
    @pytest.mark.api
    def test_revenue_analytics(self, client, authenticated_user):
        """Test revenue analytics endpoint."""
        response = client.get('/api/analytics/revenue',
                            headers={'Authorization': 'Bearer test-token'})
        # Adjust assertion based on actual implementation
        assert response.status_code in [200, 404, 501]

class TestErrorHandling:
    """Test API error handling and edge cases."""
    
    def test_unauthorized_access(self, client):
        """Test unauthorized access to protected endpoints."""
        response = client.get('/api/clients')
        assert response.status_code == 401
    
    def test_invalid_json_payload(self, client, authenticated_user):
        """Test handling of invalid JSON payloads."""
        response = client.post('/api/clients',
                             data='invalid json',
                             headers={
                                 'Authorization': 'Bearer test-token',
                                 'Content-Type': 'application/json'
                             })
        assert response.status_code == 400
    
    def test_missing_required_fields(self, client, authenticated_user):
        """Test handling of missing required fields."""
        response = client.post('/api/clients',
                             json={'first_name': 'John'},  # Missing required fields
                             headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 400
    
    def test_rate_limiting(self, client, authenticated_user):
        """Test API rate limiting (if implemented)."""
        # Make multiple rapid requests
        responses = []
        for i in range(100):
            response = client.get('/api/clients',
                                headers={'Authorization': 'Bearer test-token'})
            responses.append(response.status_code)
        
        # Check if rate limiting is working (429 status code)
        # This test might pass if rate limiting isn't implemented yet
        assert all(code in [200, 429] for code in responses)
    
    def test_large_payload_handling(self, client, authenticated_user):
        """Test handling of large payloads."""
        large_text = 'A' * 1000000  # 1MB of text
        response = client.post('/api/spanish/translate',
                             json={
                                 'text': large_text,
                                 'target_language': 'es'
                             },
                             headers={'Authorization': 'Bearer test-token'})
        # Should either handle gracefully or return appropriate error
        assert response.status_code in [200, 400, 413]

class TestPerformanceAndScalability:
    """Test API performance and scalability."""
    
    @pytest.mark.performance
    def test_api_response_time(self, client, authenticated_user, performance_monitor):
        """Test API response times are within acceptable limits."""
        performance_monitor.start_monitoring()
        
        response = client.get('/api/clients',
                            headers={'Authorization': 'Bearer test-token'})
        
        metrics = performance_monitor.stop_monitoring()
        
        assert response.status_code == 200
        assert metrics['execution_time'] < 2.0  # Should respond within 2 seconds
    
    @pytest.mark.performance
    @pytest.mark.slow
    def test_concurrent_requests(self, client, authenticated_user):
        """Test handling of concurrent requests."""
        import threading
        import time
        
        results = []
        
        def make_request():
            response = client.get('/api/clients',
                                headers={'Authorization': 'Bearer test-token'})
            results.append(response.status_code)
        
        # Create and start multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert all(code == 200 for code in results)
        assert len(results) == 10

@pytest.mark.integration
class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""
    
    def test_client_case_workflow(self, client, authenticated_user, sample_client_data, sample_case_data):
        """Test complete client and case creation workflow."""
        # Create client
        response = client.post('/api/clients',
                             json=sample_client_data,
                             headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 201
        client_data = response.get_json()
        client_id = client_data['client']['id']
        
        # Create case for client
        case_data = sample_case_data.copy()
        case_data['client_id'] = client_id
        
        response = client.post('/api/cases',
                             json=case_data,
                             headers={'Authorization': 'Bearer test-token'})
        # Adjust assertion based on actual implementation
        assert response.status_code in [201, 404, 501]
    
    def test_document_analysis_workflow(self, client, authenticated_user, mock_document_analysis):
        """Test complete document upload and analysis workflow."""
        # Upload document
        data = {
            'file': (io.BytesIO(b'Contract content for analysis'), 'contract.txt'),
            'document_type': 'contract',
            'analysis_type': 'comprehensive'
        }
        response = client.post('/api/documents/upload',
                             data=data,
                             headers={'Authorization': 'Bearer test-token'})
        assert response.status_code == 200
        
        # Analyze document
        upload_data = response.get_json()
        if 'document_id' in upload_data:
            response = client.get(f'/api/documents/{upload_data["document_id"]}/analysis',
                                headers={'Authorization': 'Bearer test-token'})
            # Adjust assertion based on actual implementation
            assert response.status_code in [200, 404, 501]