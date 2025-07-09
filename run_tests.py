#!/usr/bin/env python3
"""
LexAI Test Runner
Production-ready test execution with comprehensive reporting
"""

import sys
import os
import subprocess
import time
from datetime import datetime
import json

def ensure_reports_directory():
    """Ensure reports directory exists."""
    reports_dir = 'reports'
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    return reports_dir

def run_security_tests():
    """Run security tests with bandit and safety."""
    print("🔒 Running Security Tests...")
    
    security_results = {
        'bandit': {'passed': False, 'issues': []},
        'safety': {'passed': False, 'issues': []}
    }
    
    # Run bandit security linter
    try:
        result = subprocess.run([
            'bandit', '-r', 'api/', '-f', 'json', '-o', 'reports/bandit_report.json'
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            security_results['bandit']['passed'] = True
            print("  ✅ Bandit security scan passed")
        else:
            print("  ⚠️ Bandit found security issues")
            if os.path.exists('reports/bandit_report.json'):
                with open('reports/bandit_report.json', 'r') as f:
                    bandit_data = json.load(f)
                    security_results['bandit']['issues'] = bandit_data.get('results', [])
    
    except subprocess.TimeoutExpired:
        print("  ❌ Bandit scan timed out")
    except FileNotFoundError:
        print("  ⚠️ Bandit not installed, skipping security scan")
    
    # Run safety check for known vulnerabilities
    try:
        result = subprocess.run([
            'safety', 'check', '--json', '--output', 'reports/safety_report.json'
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            security_results['safety']['passed'] = True
            print("  ✅ Safety vulnerability check passed")
        else:
            print("  ⚠️ Safety found vulnerabilities")
    
    except subprocess.TimeoutExpired:
        print("  ❌ Safety check timed out")
    except FileNotFoundError:
        print("  ⚠️ Safety not installed, skipping vulnerability check")
    
    return security_results

def run_code_quality_tests():
    """Run code quality tests."""
    print("📊 Running Code Quality Tests...")
    
    quality_results = {
        'flake8': {'passed': False},
        'complexity': {'passed': False}
    }
    
    # Run flake8 for code style
    try:
        result = subprocess.run([
            'flake8', 'api/', '--output-file=reports/flake8_report.txt', '--statistics'
        ], capture_output=True, text=True, timeout=180)
        
        if result.returncode == 0:
            quality_results['flake8']['passed'] = True
            print("  ✅ Code style check passed")
        else:
            print("  ⚠️ Code style issues found")
    
    except subprocess.TimeoutExpired:
        print("  ❌ Code style check timed out")
    except FileNotFoundError:
        print("  ⚠️ Flake8 not installed, skipping code style check")
    
    return quality_results

def run_pytest_tests(test_categories=None):
    """Run pytest tests with specified categories."""
    print("🧪 Running Pytest Tests...")
    
    base_cmd = ['python', '-m', 'pytest']
    
    if test_categories:
        if 'all' not in test_categories:
            # Build marker expression
            markers = []
            for category in test_categories:
                markers.append(category)
            
            if markers:
                marker_expr = ' or '.join(markers)
                base_cmd.extend(['-m', marker_expr])
    else:
        # Default: run all except slow tests
        base_cmd.extend(['-m', 'not slow'])
    
    # Add coverage and reporting options
    base_cmd.extend([
        '--cov=api',
        '--cov-report=html:reports/coverage_html',
        '--cov-report=term-missing',
        '--cov-report=xml:reports/coverage.xml',
        '--html=reports/pytest_report.html',
        '--self-contained-html',
        '--json-report',
        '--json-report-file=reports/pytest_report.json',
        '--tb=short'
    ])
    
    try:
        start_time = time.time()
        result = subprocess.run(base_cmd, timeout=1800)  # 30 minute timeout
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        print(f"  Test execution completed in {execution_time:.1f} seconds")
        
        if result.returncode == 0:
            print("  ✅ All tests passed")
            return True, execution_time
        else:
            print("  ❌ Some tests failed")
            return False, execution_time
    
    except subprocess.TimeoutExpired:
        print("  ❌ Tests timed out after 30 minutes")
        return False, 1800

def run_performance_benchmark():
    """Run performance benchmark tests."""
    print("⚡ Running Performance Benchmark...")
    
    try:
        result = subprocess.run([
            'python', '-m', 'pytest', 
            '-m', 'performance',
            '--benchmark-only',
            '--benchmark-json=reports/benchmark_report.json'
        ], timeout=600)  # 10 minute timeout
        
        if result.returncode == 0:
            print("  ✅ Performance benchmarks completed")
            return True
        else:
            print("  ⚠️ Some performance tests failed")
            return False
    
    except subprocess.TimeoutExpired:
        print("  ❌ Performance tests timed out")
        return False
    except FileNotFoundError:
        print("  ⚠️ pytest-benchmark not installed, skipping performance tests")
        return None

def generate_test_report(results):
    """Generate comprehensive test report."""
    report = {
        'timestamp': datetime.now().isoformat(),
        'summary': results,
        'recommendations': []
    }
    
    # Add recommendations based on results
    if not results['pytest']['passed']:
        report['recommendations'].append("Fix failing unit/integration tests before deployment")
    
    if not results['security']['bandit']['passed']:
        report['recommendations'].append("Address security issues found by Bandit")
    
    if not results['security']['safety']['passed']:
        report['recommendations'].append("Update dependencies to fix known vulnerabilities")
    
    if not results['code_quality']['flake8']['passed']:
        report['recommendations'].append("Fix code style issues for better maintainability")
    
    if results['performance'] is False:
        report['recommendations'].append("Investigate performance issues before production deployment")
    
    # Calculate overall score
    total_checks = 5
    passed_checks = sum([
        1 if results['pytest']['passed'] else 0,
        1 if results['security']['bandit']['passed'] else 0,
        1 if results['security']['safety']['passed'] else 0,
        1 if results['code_quality']['flake8']['passed'] else 0,
        1 if results['performance'] is True else 0
    ])
    
    report['overall_score'] = (passed_checks / total_checks) * 100
    report['production_ready'] = report['overall_score'] >= 80
    
    # Save report
    with open('reports/test_summary.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    return report

def print_summary(report):
    """Print test summary."""
    print("\n" + "="*60)
    print("🏛️  LEXAI PRODUCTION READINESS REPORT")
    print("="*60)
    
    print(f"📅 Report Generated: {report['timestamp']}")
    print(f"📊 Overall Score: {report['overall_score']:.1f}%")
    
    if report['production_ready']:
        print("✅ PRODUCTION READY")
    else:
        print("❌ NOT PRODUCTION READY")
    
    print("\n📋 Test Results:")
    results = report['summary']
    
    # Pytest results
    status = "✅ PASS" if results['pytest']['passed'] else "❌ FAIL"
    time_info = f" ({results['pytest']['execution_time']:.1f}s)" if 'execution_time' in results['pytest'] else ""
    print(f"  Unit/Integration Tests: {status}{time_info}")
    
    # Security results
    bandit_status = "✅ PASS" if results['security']['bandit']['passed'] else "❌ FAIL"
    safety_status = "✅ PASS" if results['security']['safety']['passed'] else "❌ FAIL"
    print(f"  Security Scan (Bandit): {bandit_status}")
    print(f"  Vulnerability Check (Safety): {safety_status}")
    
    # Code quality results
    flake8_status = "✅ PASS" if results['code_quality']['flake8']['passed'] else "❌ FAIL"
    print(f"  Code Quality (Flake8): {flake8_status}")
    
    # Performance results
    if results['performance'] is True:
        perf_status = "✅ PASS"
    elif results['performance'] is False:
        perf_status = "❌ FAIL"
    else:
        perf_status = "⚠️ SKIP"
    print(f"  Performance Tests: {perf_status}")
    
    # Recommendations
    if report['recommendations']:
        print("\n💡 Recommendations:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"  {i}. {rec}")
    
    print("\n📁 Detailed reports available in: ./reports/")
    print("  - pytest_report.html (Test Results)")
    print("  - coverage_html/index.html (Coverage Report)")
    print("  - bandit_report.json (Security Issues)")
    print("  - test_summary.json (Complete Report)")
    
    print("\n" + "="*60)

def main():
    """Main test runner."""
    print("🚀 LexAI Production Readiness Testing")
    print("="*50)
    
    # Parse command line arguments
    test_categories = []
    if len(sys.argv) > 1:
        test_categories = sys.argv[1:]
    
    # Ensure reports directory exists
    ensure_reports_directory()
    
    start_time = time.time()
    
    # Run all test categories
    results = {
        'pytest': {'passed': False},
        'security': {},
        'code_quality': {},
        'performance': None
    }
    
    # Run pytest tests
    pytest_passed, execution_time = run_pytest_tests(test_categories)
    results['pytest']['passed'] = pytest_passed
    results['pytest']['execution_time'] = execution_time
    
    # Run security tests
    results['security'] = run_security_tests()
    
    # Run code quality tests
    results['code_quality'] = run_code_quality_tests()
    
    # Run performance tests if requested
    if not test_categories or 'performance' in test_categories or 'all' in test_categories:
        results['performance'] = run_performance_benchmark()
    
    # Generate and display report
    total_time = time.time() - start_time
    
    report = generate_test_report(results)
    report['total_execution_time'] = total_time
    
    print_summary(report)
    
    # Exit with appropriate code
    if report['production_ready']:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()