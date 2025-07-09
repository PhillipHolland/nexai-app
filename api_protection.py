#!/usr/bin/env python3
"""
XAI API Connection Protection Script
Prevents accidental modifications to working API configuration
"""

import os
import re
import sys

def check_api_modifications():
    """Check if critical API configuration has been modified"""
    
    try:
        with open('/Users/phillipholland/Desktop/lexai/lexai-app/api/index.py', 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ Error: Could not find api/index.py")
        return False
    
    # Critical configuration that should not be changed
    critical_patterns = {
        'endpoint': r'https://api\.x\.ai/v1/chat/completions',
        'model': r'["\']model["\']:\s*["\']grok-3-latest["\']',
        'auth_header': r'["\']Authorization["\']:\s*f["\']Bearer\s*\{xai_api_key\}["\']',
        'content_type': r'["\']Content-Type["\']:\s*["\']application/json["\']'
    }
    
    violations = []
    
    for check_name, pattern in critical_patterns.items():
        if not re.search(pattern, content):
            violations.append(check_name)
    
    if violations:
        print("🚨 CRITICAL API CONFIGURATION MISSING OR MODIFIED!")
        print("=" * 60)
        print("The following critical configurations are missing:")
        for violation in violations:
            print(f"❌ {violation}")
        
        print("\n📋 REQUIRED CONFIGURATION:")
        print("Endpoint: https://api.x.ai/v1/chat/completions")
        print("Model: grok-3-latest")
        print("Headers: Authorization: Bearer + Content-Type: application/json")
        
        print("\n🔧 ACTION REQUIRED:")
        print("1. Restore the working API configuration")
        print("2. Check API_CONNECTION_LOCK.md for reference")
        print("3. Test with user's curl command")
        
        return False
    else:
        print("✅ XAI API configuration is intact and should be working")
        return True

def main():
    """Main API protection check"""
    print("🔐 Checking XAI API connection integrity...")
    
    if check_api_modifications():
        print("🎉 API connection configuration is safe!")
        return 0
    else:
        print("⚠️  API connection may be broken!")
        return 1

if __name__ == "__main__":
    sys.exit(main())