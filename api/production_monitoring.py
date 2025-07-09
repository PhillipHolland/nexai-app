#!/usr/bin/env python3
"""
Production Monitoring and Performance Optimization Module
Real-time monitoring, performance tracking, and optimization for LexAI
"""

import os
import time
import logging
import json
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from functools import wraps
import weakref
from collections import defaultdict, deque
import sqlite3

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Real-time performance monitoring system."""
    
    def __init__(self, max_history=1000):
        self.max_history = max_history
        self.metrics = defaultdict(lambda: deque(maxlen=max_history))
        self.alert_thresholds = {
            'response_time': 5.0,      # 5 seconds
            'memory_usage': 80.0,      # 80% memory usage
            'cpu_usage': 85.0,         # 85% CPU usage
            'error_rate': 5.0,         # 5% error rate
            'disk_usage': 90.0         # 90% disk usage
        }
        self.active_requests = weakref.WeakSet()
        self._lock = threading.Lock()
        self._monitoring_active = True
        
        # Start background monitoring
        self._start_system_monitoring()
    
    def _start_system_monitoring(self):
        """Start background system monitoring."""
        def monitor_system():
            while self._monitoring_active:
                try:
                    # CPU usage
                    cpu_percent = psutil.cpu_percent(interval=1)
                    self.record_metric('system_cpu', cpu_percent)
                    
                    # Memory usage
                    memory = psutil.virtual_memory()
                    self.record_metric('system_memory_percent', memory.percent)
                    self.record_metric('system_memory_used', memory.used / 1024 / 1024)  # MB
                    
                    # Disk usage
                    disk = psutil.disk_usage('/')
                    disk_percent = (disk.used / disk.total) * 100
                    self.record_metric('system_disk_percent', disk_percent)
                    
                    # Network I/O
                    net_io = psutil.net_io_counters()
                    self.record_metric('network_bytes_sent', net_io.bytes_sent)
                    self.record_metric('network_bytes_recv', net_io.bytes_recv)
                    
                    # Check for alerts
                    self._check_alerts()
                    
                except Exception as e:
                    logger.error(f"System monitoring error: {e}")
                
                time.sleep(30)  # Monitor every 30 seconds
        
        monitor_thread = threading.Thread(target=monitor_system, daemon=True)
        monitor_thread.start()
    
    def record_metric(self, metric_name: str, value: float, timestamp: Optional[datetime] = None):
        """Record a performance metric."""
        if timestamp is None:
            timestamp = datetime.now()
        
        with self._lock:
            self.metrics[metric_name].append({
                'value': value,
                'timestamp': timestamp.isoformat()
            })
    
    def get_metric_stats(self, metric_name: str, time_window: Optional[timedelta] = None) -> Dict[str, Any]:
        """Get statistical summary of a metric."""
        with self._lock:
            data = list(self.metrics[metric_name])
        
        if not data:
            return {'count': 0, 'avg': 0, 'min': 0, 'max': 0, 'latest': 0}
        
        # Filter by time window if specified
        if time_window:
            cutoff_time = datetime.now() - time_window
            data = [
                d for d in data 
                if datetime.fromisoformat(d['timestamp']) >= cutoff_time
            ]
        
        if not data:
            return {'count': 0, 'avg': 0, 'min': 0, 'max': 0, 'latest': 0}
        
        values = [d['value'] for d in data]
        
        return {
            'count': len(values),
            'avg': sum(values) / len(values),
            'min': min(values),
            'max': max(values),
            'latest': values[-1] if values else 0,
            'p95': self._percentile(values, 95),
            'p99': self._percentile(values, 99)
        }
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]
    
    def _check_alerts(self):
        """Check for performance alerts."""
        alerts = []
        
        # Check CPU usage
        cpu_stats = self.get_metric_stats('system_cpu', timedelta(minutes=5))
        if cpu_stats['avg'] > self.alert_thresholds['cpu_usage']:
            alerts.append({
                'type': 'high_cpu',
                'message': f"High CPU usage: {cpu_stats['avg']:.1f}%",
                'severity': 'warning'
            })
        
        # Check memory usage
        memory_stats = self.get_metric_stats('system_memory_percent', timedelta(minutes=5))
        if memory_stats['avg'] > self.alert_thresholds['memory_usage']:
            alerts.append({
                'type': 'high_memory',
                'message': f"High memory usage: {memory_stats['avg']:.1f}%",
                'severity': 'warning'
            })
        
        # Check response times
        response_stats = self.get_metric_stats('response_time', timedelta(minutes=10))
        if response_stats['avg'] > self.alert_thresholds['response_time']:
            alerts.append({
                'type': 'slow_response',
                'message': f"Slow response times: {response_stats['avg']:.2f}s avg",
                'severity': 'critical'
            })
        
        # Log alerts
        for alert in alerts:
            if alert['severity'] == 'critical':
                logger.critical(f"ALERT: {alert['message']}")
            else:
                logger.warning(f"ALERT: {alert['message']}")
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get monitoring data for dashboard display."""
        now = datetime.now()
        last_hour = timedelta(hours=1)
        last_day = timedelta(days=1)
        
        return {
            'timestamp': now.isoformat(),
            'system': {
                'cpu': self.get_metric_stats('system_cpu', last_hour),
                'memory': self.get_metric_stats('system_memory_percent', last_hour),
                'disk': self.get_metric_stats('system_disk_percent', last_hour)
            },
            'application': {
                'response_time': self.get_metric_stats('response_time', last_hour),
                'request_count': self.get_metric_stats('request_count', last_hour),
                'error_rate': self.get_metric_stats('error_rate', last_hour),
                'active_users': self.get_metric_stats('active_users', last_hour)
            },
            'trends': {
                'daily_requests': self.get_metric_stats('request_count', last_day),
                'daily_errors': self.get_metric_stats('error_count', last_day),
                'daily_response_time': self.get_metric_stats('response_time', last_day)
            }
        }
    
    def shutdown(self):
        """Shutdown monitoring."""
        self._monitoring_active = False

# Global monitor instance
performance_monitor = PerformanceMonitor()

def monitor_performance(func):
    """Decorator to monitor function performance."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        error_occurred = False
        
        try:
            # Track active request
            request_info = {
                'function': func.__name__,
                'start_time': start_time,
                'args_count': len(args),
                'kwargs_count': len(kwargs)
            }
            performance_monitor.active_requests.add(request_info)
            
            # Execute function
            result = func(*args, **kwargs)
            
            return result
            
        except Exception as e:
            error_occurred = True
            performance_monitor.record_metric('error_count', 1)
            raise
            
        finally:
            # Record performance metrics
            end_time = time.time()
            execution_time = end_time - start_time
            
            performance_monitor.record_metric('response_time', execution_time)
            performance_monitor.record_metric('request_count', 1)
            
            if error_occurred:
                performance_monitor.record_metric('error_rate', 1)
            else:
                performance_monitor.record_metric('error_rate', 0)
            
            # Log slow requests
            if execution_time > 3.0:
                logger.warning(f"Slow request: {func.__name__} took {execution_time:.2f}s")
    
    return wrapper

class CacheManager:
    """Simple in-memory cache with TTL support."""
    
    def __init__(self, default_ttl=300):  # 5 minutes default
        self.cache = {}
        self.ttl_data = {}
        self.default_ttl = default_ttl
        self._lock = threading.Lock()
        
        # Start cleanup thread
        self._start_cleanup_thread()
    
    def _start_cleanup_thread(self):
        """Start background cache cleanup."""
        def cleanup():
            while True:
                try:
                    self._cleanup_expired()
                    time.sleep(60)  # Cleanup every minute
                except Exception as e:
                    logger.error(f"Cache cleanup error: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup, daemon=True)
        cleanup_thread.start()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            if key not in self.cache:
                return None
            
            # Check TTL
            if key in self.ttl_data:
                if time.time() > self.ttl_data[key]:
                    del self.cache[key]
                    del self.ttl_data[key]
                    return None
            
            return self.cache[key]
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        if ttl is None:
            ttl = self.default_ttl
        
        with self._lock:
            self.cache[key] = value
            if ttl > 0:
                self.ttl_data[key] = time.time() + ttl
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        with self._lock:
            deleted = key in self.cache
            self.cache.pop(key, None)
            self.ttl_data.pop(key, None)
            return deleted
    
    def clear(self) -> None:
        """Clear all cache."""
        with self._lock:
            self.cache.clear()
            self.ttl_data.clear()
    
    def _cleanup_expired(self):
        """Remove expired cache entries."""
        current_time = time.time()
        expired_keys = []
        
        with self._lock:
            for key, expiry_time in self.ttl_data.items():
                if current_time > expiry_time:
                    expired_keys.append(key)
            
            for key in expired_keys:
                self.cache.pop(key, None)
                self.ttl_data.pop(key, None)
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_keys = len(self.cache)
            expired_keys = sum(
                1 for exp_time in self.ttl_data.values() 
                if time.time() > exp_time
            )
            
            return {
                'total_keys': total_keys,
                'expired_keys': expired_keys,
                'active_keys': total_keys - expired_keys,
                'memory_usage_bytes': sum(
                    len(str(k)) + len(str(v)) 
                    for k, v in self.cache.items()
                )
            }

# Global cache instance
cache_manager = CacheManager()

def cache_result(ttl=300, key_generator=None):
    """Decorator to cache function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_generator:
                cache_key = key_generator(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Try to get from cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                performance_monitor.record_metric('cache_hit', 1)
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            performance_monitor.record_metric('cache_miss', 1)
            
            return result
        
        return wrapper
    return decorator

class SecurityAuditLogger:
    """Security event logging and monitoring."""
    
    def __init__(self, log_file="logs/security_audit.log"):
        self.log_file = log_file
        self.setup_logging()
        self.suspicious_patterns = {
            'sql_injection': [
                r"union\s+select", r"drop\s+table", r"delete\s+from",
                r"insert\s+into", r"update\s+.*set", r"exec\s*\("
            ],
            'xss_attempt': [
                r"<script", r"javascript:", r"onerror=", r"onload=",
                r"alert\s*\(", r"document\.cookie"
            ],
            'path_traversal': [
                r"\.\./", r"\.\.\\", r"/etc/passwd", r"/proc/",
                r"C:\\Windows", r"\.\.%2f"
            ],
            'command_injection': [
                r";\s*ls", r";\s*cat", r";\s*rm", r"\|\s*cat",
                r"&&\s*rm", r"`.*`", r"\$\(.*\)"
            ]
        }
    
    def setup_logging(self):
        """Setup security audit logging."""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        self.security_logger = logging.getLogger('security_audit')
        self.security_logger.setLevel(logging.INFO)
        
        # Create file handler
        handler = logging.FileHandler(self.log_file)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.security_logger.addHandler(handler)
    
    def log_security_event(self, event_type: str, details: Dict[str, Any], 
                          severity: str = 'info', user_id: Optional[str] = None):
        """Log a security event."""
        event_data = {
            'event_type': event_type,
            'severity': severity,
            'user_id': user_id,
            'timestamp': datetime.now().isoformat(),
            'details': details
        }
        
        log_message = json.dumps(event_data)
        
        if severity == 'critical':
            self.security_logger.critical(log_message)
        elif severity == 'warning':
            self.security_logger.warning(log_message)
        else:
            self.security_logger.info(log_message)
        
        # Record metric for monitoring
        performance_monitor.record_metric(f'security_event_{event_type}', 1)
    
    def analyze_input(self, input_data: str, context: str = '') -> List[str]:
        """Analyze input for suspicious patterns."""
        threats_detected = []
        input_lower = input_data.lower()
        
        for threat_type, patterns in self.suspicious_patterns.items():
            for pattern in patterns:
                import re
                if re.search(pattern, input_lower, re.IGNORECASE):
                    threats_detected.append(threat_type)
                    
                    # Log security event
                    self.log_security_event(
                        event_type=f'suspicious_input_{threat_type}',
                        details={
                            'pattern_matched': pattern,
                            'input_context': context,
                            'input_length': len(input_data)
                        },
                        severity='warning'
                    )
                    break
        
        return threats_detected

# Global security logger
security_logger = SecurityAuditLogger()

class HealthChecker:
    """Application health checking and monitoring."""
    
    def __init__(self):
        self.health_checks = {}
        self.last_check_results = {}
    
    def register_check(self, name: str, check_func, critical: bool = False):
        """Register a health check function."""
        self.health_checks[name] = {
            'function': check_func,
            'critical': critical
        }
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all registered health checks."""
        results = {}
        overall_status = 'healthy'
        critical_failures = []
        
        for name, check_info in self.health_checks.items():
            try:
                start_time = time.time()
                result = check_info['function']()
                check_time = time.time() - start_time
                
                if isinstance(result, bool):
                    status = 'pass' if result else 'fail'
                    details = None
                elif isinstance(result, dict):
                    status = result.get('status', 'fail')
                    details = result.get('details')
                else:
                    status = 'fail'
                    details = str(result)
                
                results[name] = {
                    'status': status,
                    'check_time': check_time,
                    'details': details,
                    'critical': check_info['critical']
                }
                
                # Track critical failures
                if status == 'fail' and check_info['critical']:
                    critical_failures.append(name)
                    overall_status = 'unhealthy'
                elif status == 'fail':
                    overall_status = 'degraded'
                
            except Exception as e:
                results[name] = {
                    'status': 'error',
                    'error': str(e),
                    'critical': check_info['critical']
                }
                
                if check_info['critical']:
                    critical_failures.append(name)
                    overall_status = 'unhealthy'
        
        self.last_check_results = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': overall_status,
            'critical_failures': critical_failures,
            'checks': results
        }
        
        return self.last_check_results
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status."""
        if not self.last_check_results:
            return {'status': 'unknown', 'message': 'No health checks performed yet'}
        
        return self.last_check_results

# Global health checker
health_checker = HealthChecker()

# Register default health checks
def check_database_connection():
    """Check database connectivity."""
    try:
        from api.database_models import db
        result = db.session.execute('SELECT 1').scalar()
        return result == 1
    except Exception as e:
        return {'status': 'fail', 'details': str(e)}

def check_memory_usage():
    """Check memory usage."""
    memory = psutil.virtual_memory()
    if memory.percent > 90:
        return {'status': 'fail', 'details': f'Memory usage at {memory.percent}%'}
    elif memory.percent > 80:
        return {'status': 'warning', 'details': f'Memory usage at {memory.percent}%'}
    else:
        return {'status': 'pass', 'details': f'Memory usage at {memory.percent}%'}

def check_disk_space():
    """Check available disk space."""
    disk = psutil.disk_usage('/')
    usage_percent = (disk.used / disk.total) * 100
    
    if usage_percent > 95:
        return {'status': 'fail', 'details': f'Disk usage at {usage_percent:.1f}%'}
    elif usage_percent > 85:
        return {'status': 'warning', 'details': f'Disk usage at {usage_percent:.1f}%'}
    else:
        return {'status': 'pass', 'details': f'Disk usage at {usage_percent:.1f}%'}

# Register default health checks
health_checker.register_check('database', check_database_connection, critical=True)
health_checker.register_check('memory', check_memory_usage, critical=False)
health_checker.register_check('disk_space', check_disk_space, critical=False)

def get_production_status() -> Dict[str, Any]:
    """Get comprehensive production status."""
    return {
        'timestamp': datetime.now().isoformat(),
        'performance': performance_monitor.get_dashboard_data(),
        'health': health_checker.get_health_status(),
        'cache': cache_manager.get_stats(),
        'version': '2.1',
        'environment': os.environ.get('ENVIRONMENT', 'development')
    }

# Cleanup on shutdown
import atexit

def cleanup_monitoring():
    """Cleanup monitoring resources."""
    try:
        performance_monitor.shutdown()
        cache_manager.clear()
        logger.info("Production monitoring cleanup completed")
    except Exception as e:
        logger.error(f"Error during monitoring cleanup: {e}")

atexit.register(cleanup_monitoring)