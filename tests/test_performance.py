"""
Performance Testing Suite
Comprehensive performance tests for LexAI production deployment
"""

import pytest
import time
import threading
import concurrent.futures
from unittest.mock import patch, Mock
import psutil
import os
import json

@pytest.mark.performance
class TestResponseTimePerformance:
    """Test API response time performance."""
    
    def test_basic_endpoint_response_time(self, client, authenticated_user):
        """Test basic endpoints respond within acceptable time limits."""
        endpoints = [
            '/api/status',
            '/api/clients',
            '/dashboard',
            '/'
        ]
        
        for endpoint in endpoints:
            start_time = time.time()
            
            if endpoint.startswith('/api/'):
                response = client.get(endpoint, headers={'Authorization': 'Bearer test-token'})
            else:
                response = client.get(endpoint)
            
            end_time = time.time()
            response_time = end_time - start_time
            
            # Basic endpoints should respond within 1 second
            assert response_time < 1.0, f"Endpoint {endpoint} took {response_time:.2f}s"
            assert response.status_code in [200, 401]  # 401 is acceptable for auth-required endpoints
    
    @pytest.mark.slow
    def test_ai_service_response_time(self, client, authenticated_user, mock_document_analysis):
        """Test AI service response times."""
        start_time = time.time()
        
        response = client.post('/api/documents/analyze',
                             json={
                                 'text': 'Sample contract text for analysis',
                                 'document_type': 'contract',
                                 'analysis_depth': 'basic'
                             },
                             headers={'Authorization': 'Bearer test-token'})
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # AI services should respond within 5 seconds
        assert response_time < 5.0, f"AI analysis took {response_time:.2f}s"
        assert response.status_code == 200
    
    @pytest.mark.slow
    def test_file_upload_performance(self, client, authenticated_user):
        """Test file upload performance."""
        # Create test file content (1MB)
        large_content = b'A' * (1024 * 1024)  # 1MB file
        
        start_time = time.time()
        
        response = client.post('/api/documents/upload',
                             data={
                                 'file': (large_content, 'large_test.txt'),
                                 'document_type': 'contract'
                             },
                             headers={'Authorization': 'Bearer test-token'})
        
        end_time = time.time()
        upload_time = end_time - start_time
        
        # 1MB upload should complete within 10 seconds
        assert upload_time < 10.0, f"1MB upload took {upload_time:.2f}s"
        # Should either succeed or fail gracefully
        assert response.status_code in [200, 400, 413, 422]
    
    def test_database_query_performance(self, client, authenticated_user, sample_client):
        """Test database query performance."""
        start_time = time.time()
        
        response = client.get('/api/clients',
                            headers={'Authorization': 'Bearer test-token'})
        
        end_time = time.time()
        query_time = end_time - start_time
        
        # Database queries should be fast
        assert query_time < 0.5, f"Database query took {query_time:.2f}s"
        assert response.status_code == 200

@pytest.mark.performance
class TestConcurrencyPerformance:
    """Test concurrent user and request handling."""
    
    @pytest.mark.slow
    def test_concurrent_api_requests(self, client, authenticated_user):
        """Test handling of concurrent API requests."""
        num_threads = 20
        num_requests_per_thread = 5
        results = []
        
        def make_requests():
            thread_results = []
            for _ in range(num_requests_per_thread):
                start_time = time.time()
                response = client.get('/api/status')
                end_time = time.time()
                
                thread_results.append({
                    'status_code': response.status_code,
                    'response_time': end_time - start_time
                })
            return thread_results
        
        # Execute concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(make_requests) for _ in range(num_threads)]
            
            for future in concurrent.futures.as_completed(futures):
                results.extend(future.result())
        
        # Analyze results
        total_requests = len(results)
        successful_requests = sum(1 for r in results if r['status_code'] == 200)
        avg_response_time = sum(r['response_time'] for r in results) / total_requests
        max_response_time = max(r['response_time'] for r in results)
        
        # Performance assertions
        assert total_requests == num_threads * num_requests_per_thread
        assert successful_requests / total_requests >= 0.95  # 95% success rate
        assert avg_response_time < 2.0  # Average response time under 2s
        assert max_response_time < 5.0  # No request takes more than 5s
    
    @pytest.mark.slow
    def test_concurrent_user_sessions(self, client, app):
        """Test multiple concurrent user sessions."""
        num_users = 10
        results = []
        
        def simulate_user_session(user_id):
            session_results = {
                'user_id': user_id,
                'login_time': None,
                'requests': [],
                'errors': 0
            }
            
            try:
                # Simulate login
                start_time = time.time()
                login_response = client.post('/api/auth/login', json={
                    'email': f'testuser{user_id}@example.com',
                    'password': 'TestPassword123!'
                })
                session_results['login_time'] = time.time() - start_time
                
                if login_response.status_code not in [200, 401]:  # 401 expected for non-existent users
                    session_results['errors'] += 1
                
                # Simulate various API calls
                api_calls = [
                    '/api/status',
                    '/api/clients',
                    '/dashboard'
                ]
                
                for endpoint in api_calls:
                    start_time = time.time()
                    if endpoint.startswith('/api/'):
                        response = client.get(endpoint, headers={'Authorization': 'Bearer test-token'})
                    else:
                        response = client.get(endpoint)
                    
                    request_time = time.time() - start_time
                    session_results['requests'].append({
                        'endpoint': endpoint,
                        'status_code': response.status_code,
                        'response_time': request_time
                    })
                    
                    if response.status_code >= 500:
                        session_results['errors'] += 1
            
            except Exception as e:
                session_results['errors'] += 1
                session_results['exception'] = str(e)
            
            return session_results
        
        # Execute concurrent user sessions
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = [executor.submit(simulate_user_session, i) for i in range(num_users)]
            
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
        
        # Analyze session results
        total_errors = sum(r['errors'] for r in results)
        total_requests = sum(len(r['requests']) for r in results)
        
        # Performance assertions
        assert len(results) == num_users
        assert total_errors / max(total_requests, 1) < 0.05  # Less than 5% error rate
    
    def test_memory_usage_under_load(self, client, authenticated_user):
        """Test memory usage under load."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Generate load
        for i in range(100):
            response = client.get('/api/status')
            assert response.status_code == 200
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB for 100 requests)
        assert memory_increase < 50 * 1024 * 1024, f"Memory increased by {memory_increase / 1024 / 1024:.1f}MB"

@pytest.mark.performance
class TestScalabilityPerformance:
    """Test application scalability characteristics."""
    
    @pytest.mark.slow
    def test_large_dataset_handling(self, client, authenticated_user, app):
        """Test performance with large datasets."""
        from api.database_models import Client, db
        
        with app.app_context():
            # Create many test clients
            clients = []
            for i in range(1000):
                client_obj = Client(
                    first_name=f'Client{i}',
                    last_name='Test',
                    email=f'client{i}@example.com',
                    attorney_id=authenticated_user.id
                )
                clients.append(client_obj)
            
            db.session.add_all(clients)
            db.session.commit()
            
            # Test querying large dataset
            start_time = time.time()
            response = client.get('/api/clients',
                                headers={'Authorization': 'Bearer test-token'})
            query_time = time.time() - start_time
            
            # Should handle large datasets efficiently
            assert query_time < 3.0, f"Large dataset query took {query_time:.2f}s"
            assert response.status_code == 200
            
            # Clean up
            Client.query.filter(Client.email.like('client%@example.com')).delete()
            db.session.commit()
    
    @pytest.mark.slow
    def test_file_processing_scalability(self, client, authenticated_user):
        """Test file processing with multiple files."""
        files_to_process = 10
        results = []
        
        def upload_file(file_index):
            content = f'Test document content {file_index} ' * 100  # Varied content
            
            start_time = time.time()
            response = client.post('/api/documents/upload',
                                 data={
                                     'file': (content.encode(), f'test{file_index}.txt'),
                                     'document_type': 'contract'
                                 },
                                 headers={'Authorization': 'Bearer test-token'})
            
            processing_time = time.time() - start_time
            
            return {
                'file_index': file_index,
                'status_code': response.status_code,
                'processing_time': processing_time
            }
        
        # Process files concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(upload_file, i) for i in range(files_to_process)]
            
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
        
        # Analyze processing performance
        successful_uploads = sum(1 for r in results if r['status_code'] in [200, 201])
        avg_processing_time = sum(r['processing_time'] for r in results) / len(results)
        max_processing_time = max(r['processing_time'] for r in results)
        
        # Performance assertions
        assert successful_uploads / files_to_process >= 0.8  # 80% success rate
        assert avg_processing_time < 5.0  # Average under 5 seconds
        assert max_processing_time < 15.0  # No upload takes more than 15 seconds

@pytest.mark.performance
class TestResourceUtilizationPerformance:
    """Test resource utilization and efficiency."""
    
    def test_cpu_usage_efficiency(self, client, authenticated_user):
        """Test CPU usage during normal operations."""
        process = psutil.Process(os.getpid())
        
        # Measure CPU usage during requests
        cpu_percentages = []
        
        for i in range(50):
            start_cpu = process.cpu_percent()
            
            response = client.get('/api/status')
            assert response.status_code == 200
            
            # Small delay to allow CPU measurement
            time.sleep(0.01)
            end_cpu = process.cpu_percent()
            
            cpu_percentages.append(end_cpu)
        
        avg_cpu = sum(cpu_percentages) / len(cpu_percentages)
        max_cpu = max(cpu_percentages)
        
        # CPU usage should be reasonable
        assert avg_cpu < 50.0, f"Average CPU usage too high: {avg_cpu:.1f}%"
        assert max_cpu < 80.0, f"Peak CPU usage too high: {max_cpu:.1f}%"
    
    def test_memory_leak_detection(self, client, authenticated_user):
        """Test for memory leaks during repeated operations."""
        process = psutil.Process(os.getpid())
        
        # Baseline memory
        baseline_memory = process.memory_info().rss
        memory_measurements = [baseline_memory]
        
        # Perform repeated operations
        for i in range(200):
            response = client.get('/api/status')
            assert response.status_code == 200
            
            # Measure memory every 20 requests
            if i % 20 == 0:
                current_memory = process.memory_info().rss
                memory_measurements.append(current_memory)
        
        # Analyze memory trend
        memory_increase = memory_measurements[-1] - memory_measurements[0]
        
        # Memory should not increase significantly (less than 20MB)
        assert memory_increase < 20 * 1024 * 1024, f"Memory leak detected: {memory_increase / 1024 / 1024:.1f}MB increase"
    
    def test_database_connection_efficiency(self, client, authenticated_user, app):
        """Test database connection management efficiency."""
        with app.app_context():
            from api.database_models import db
            
            # Monitor database connections during operations
            initial_connections = len(db.engine.pool.checkedout())
            
            # Perform database operations
            for i in range(50):
                response = client.get('/api/clients',
                                    headers={'Authorization': 'Bearer test-token'})
                assert response.status_code == 200
            
            final_connections = len(db.engine.pool.checkedout())
            
            # Connection pool should be managed efficiently
            connection_increase = final_connections - initial_connections
            assert connection_increase <= 5, f"Too many connections created: {connection_increase}"

@pytest.mark.performance
class TestCachePerformance:
    """Test caching mechanisms and performance."""
    
    def test_static_content_caching(self, client):
        """Test static content caching performance."""
        static_endpoints = [
            '/static/landing.css',
            '/static/favicon.ico'
        ]
        
        for endpoint in static_endpoints:
            # First request
            start_time = time.time()
            response1 = client.get(endpoint)
            first_request_time = time.time() - start_time
            
            # Second request (should be faster if cached)
            start_time = time.time()
            response2 = client.get(endpoint)
            second_request_time = time.time() - start_time
            
            # Both requests should succeed or both should fail consistently
            assert response1.status_code == response2.status_code
            
            # If successful, second request should be faster or same speed
            if response1.status_code == 200:
                # Second request should not be significantly slower
                assert second_request_time <= first_request_time * 1.5
    
    @pytest.mark.slow
    def test_api_response_caching(self, client, authenticated_user):
        """Test API response caching where applicable."""
        # Test endpoints that could benefit from caching
        cacheable_endpoints = [
            '/api/status',
            '/api/spanish/ui-translations?language=es'
        ]
        
        for endpoint in cacheable_endpoints:
            # Make multiple requests to the same endpoint
            response_times = []
            
            for i in range(5):
                start_time = time.time()
                
                if endpoint.startswith('/api/spanish/'):
                    response = client.get(endpoint, headers={'Authorization': 'Bearer test-token'})
                else:
                    response = client.get(endpoint)
                
                response_time = time.time() - start_time
                response_times.append(response_time)
                
                # All responses should be consistent
                assert response.status_code in [200, 401, 404]
            
            # Later requests should not be significantly slower than first
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            
            assert max_response_time <= avg_response_time * 2.0, f"Inconsistent response times for {endpoint}"

@pytest.mark.performance
class TestLoadPerformance:
    """Test performance under various load conditions."""
    
    @pytest.mark.slow
    def test_sustained_load_performance(self, client, authenticated_user):
        """Test performance under sustained load."""
        duration_seconds = 30  # 30-second test
        start_time = time.time()
        request_count = 0
        error_count = 0
        response_times = []
        
        while time.time() - start_time < duration_seconds:
            request_start = time.time()
            
            try:
                response = client.get('/api/status')
                response_time = time.time() - request_start
                response_times.append(response_time)
                
                if response.status_code != 200:
                    error_count += 1
                
                request_count += 1
                
                # Small delay to prevent overwhelming
                time.sleep(0.1)
                
            except Exception:
                error_count += 1
                request_count += 1
        
        # Calculate performance metrics
        total_time = time.time() - start_time
        requests_per_second = request_count / total_time
        error_rate = error_count / request_count if request_count > 0 else 1
        avg_response_time = sum(response_times) / len(response_times) if response_times else float('inf')
        
        # Performance assertions
        assert requests_per_second >= 5.0, f"Too slow: {requests_per_second:.1f} requests/second"
        assert error_rate < 0.05, f"Too many errors: {error_rate:.1%}"
        assert avg_response_time < 1.0, f"Responses too slow: {avg_response_time:.2f}s average"
    
    @pytest.mark.slow
    def test_peak_load_handling(self, client, authenticated_user):
        """Test handling of peak load conditions."""
        num_concurrent_users = 15
        requests_per_user = 10
        results = []
        
        def simulate_peak_user():
            user_results = {
                'requests_completed': 0,
                'errors': 0,
                'total_time': 0
            }
            
            start_time = time.time()
            
            for i in range(requests_per_user):
                try:
                    response = client.get('/api/status')
                    user_results['requests_completed'] += 1
                    
                    if response.status_code != 200:
                        user_results['errors'] += 1
                        
                except Exception:
                    user_results['errors'] += 1
            
            user_results['total_time'] = time.time() - start_time
            return user_results
        
        # Simulate peak load
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent_users) as executor:
            futures = [executor.submit(simulate_peak_user) for _ in range(num_concurrent_users)]
            
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
        
        # Analyze peak load results
        total_requests = sum(r['requests_completed'] for r in results)
        total_errors = sum(r['errors'] for r in results)
        total_time = max(r['total_time'] for r in results)
        
        error_rate = total_errors / total_requests if total_requests > 0 else 1
        throughput = total_requests / total_time
        
        # Peak load assertions
        assert error_rate < 0.1, f"High error rate under peak load: {error_rate:.1%}"
        assert throughput >= 30.0, f"Low throughput under peak load: {throughput:.1f} requests/second"
        assert all(r['requests_completed'] > 0 for r in results), "Some users completed no requests"

@pytest.mark.performance
class TestPerformanceRegression:
    """Test for performance regressions."""
    
    def test_baseline_performance_metrics(self, client, authenticated_user):
        """Establish baseline performance metrics."""
        # Define performance baselines
        performance_baselines = {
            'api_status_response_time': 0.1,      # 100ms
            'client_list_response_time': 0.5,     # 500ms
            'dashboard_load_time': 1.0,           # 1 second
            'login_response_time': 0.3             # 300ms
        }
        
        actual_performance = {}
        
        # Test API status
        start_time = time.time()
        response = client.get('/api/status')
        actual_performance['api_status_response_time'] = time.time() - start_time
        assert response.status_code == 200
        
        # Test client list
        start_time = time.time()
        response = client.get('/api/clients', headers={'Authorization': 'Bearer test-token'})
        actual_performance['client_list_response_time'] = time.time() - start_time
        assert response.status_code == 200
        
        # Test dashboard load
        start_time = time.time()
        response = client.get('/dashboard')
        actual_performance['dashboard_load_time'] = time.time() - start_time
        # Dashboard might require authentication
        assert response.status_code in [200, 302, 401]
        
        # Test login
        start_time = time.time()
        response = client.post('/api/auth/login', json={
            'email': 'test@example.com',
            'password': 'wrong_password'
        })
        actual_performance['login_response_time'] = time.time() - start_time
        # Expecting failure but measuring response time
        assert response.status_code in [401, 422]
        
        # Compare against baselines
        for metric, baseline in performance_baselines.items():
            actual = actual_performance.get(metric, float('inf'))
            # Allow 50% degradation from baseline
            assert actual <= baseline * 1.5, f"{metric}: {actual:.3f}s exceeds baseline {baseline:.3f}s"
    
    def test_performance_monitoring_data(self, client, authenticated_user, performance_monitor):
        """Collect performance monitoring data."""
        performance_monitor.start_monitoring()
        
        # Perform standard operations
        operations = [
            lambda: client.get('/api/status'),
            lambda: client.get('/api/clients', headers={'Authorization': 'Bearer test-token'}),
            lambda: client.post('/api/spanish/translate', 
                              json={'text': 'test', 'target_language': 'es'},
                              headers={'Authorization': 'Bearer test-token'})
        ]
        
        for operation in operations:
            response = operation()
            # Operations should complete successfully or fail gracefully
            assert response.status_code < 500
        
        metrics = performance_monitor.stop_monitoring()
        
        # Log performance metrics for monitoring
        print(f"Performance Metrics: {json.dumps(metrics, indent=2)}")
        
        # Basic performance assertions
        assert metrics['execution_time'] < 10.0, f"Operations took too long: {metrics['execution_time']:.2f}s"
        assert metrics['memory_used'] < 50 * 1024 * 1024, f"Too much memory used: {metrics['memory_used'] / 1024 / 1024:.1f}MB"