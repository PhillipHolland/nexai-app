#!/usr/bin/env python3
"""
Security Check Script for LexAI
Prevents API keys from being committed to git
"""

import os
import re
import sys
import subprocess

def check_for_api_keys():
    """Check for potential API keys in staged files"""
    try:
        # Get staged files
        result = subprocess.run(['git', 'diff', '--cached', '--name-only'], 
                              capture_output=True, text=True)
        staged_files = result.stdout.strip().split('\n')
        
        # Patterns that indicate API keys
        api_key_patterns = [
            r'xai-[A-Za-z0-9]{64,}',
            r'sk-[A-Za-z0-9]{48,}',
            r'Bearer [A-Za-z0-9]{32,}',
            r'["\']XAI_API_KEY["\']:\s*["\'][^"\']+["\']',
            r'XAI_API_KEY\s*=\s*["\'][^"\']+["\']'
        ]
        
        violations = []
        
        for file_path in staged_files:
            if not file_path or not os.path.exists(file_path):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                for pattern in api_key_patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        violations.append({
                            'file': file_path,
                            'pattern': pattern,
                            'matches': matches
                        })
                        
            except Exception as e:
                print(f"Warning: Could not read {file_path}: {e}")
                
        return violations
        
    except Exception as e:
        print(f"Error checking for API keys: {e}")
        return []

def main():
    """Main security check function"""
    print("🔐 Running security check for API keys...")
    
    violations = check_for_api_keys()
    
    if violations:
        print("\n🚨 SECURITY VIOLATION DETECTED!")
        print("=" * 50)
        print("Potential API keys found in staged files:")
        
        for violation in violations:
            print(f"\n📁 File: {violation['file']}")
            print(f"🔍 Pattern: {violation['pattern']}")
            print(f"⚠️  Matches: {len(violation['matches'])}")
            
        print("\n" + "=" * 50)
        print("🛡️  SECURITY ACTIONS REQUIRED:")
        print("1. Remove API keys from files")
        print("2. Use environment variables instead")
        print("3. Update .gitignore if needed")
        print("4. Consider using git-secrets or similar tools")
        
        print("\n❌ COMMIT BLOCKED for security reasons!")
        return 1
    else:
        print("✅ No API keys detected in staged files")
        print("🔐 Security check passed!")
        return 0

if __name__ == "__main__":
    sys.exit(main())