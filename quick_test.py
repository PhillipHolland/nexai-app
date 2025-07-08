#!/usr/bin/env python3
"""
Quick test for Bagel RL integration
"""

import requests
import json

def quick_test():
    print("🚀 Quick Bagel RL Test")
    print("=" * 30)
    
    # Test 1: Check if Bagel server is running
    print("1. Testing Bagel server...")
    try:
        response = requests.get("http://35.184.175.255:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Bagel server is running!")
            print(f"   Status: {response.json()}")
        else:
            print(f"❌ Server error: {response.status_code}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    
    # Test 2: Test local Bagel service
    print("\n2. Testing local Bagel service...")
    try:
        import sys
        sys.path.append('/Users/phillipholland/Desktop/lexai/lexai-app/api')
        from bagel_service import query_bagel_legal_ai
        
        result = query_bagel_legal_ai("What is Title VII employment discrimination?", "employment_law")
        print(f"✅ Local service working!")
        print(f"   Success: {result['success']}")
        print(f"   Source: {result['source']}")
        print(f"   Response: {result['response'][:100]}...")
        
    except Exception as e:
        print(f"❌ Local service error: {e}")
    
    # Test 3: Test a simple legal query directly to server
    print("\n3. Testing direct legal query...")
    try:
        response = requests.post(
            "http://35.184.175.255:8000/query",
            json={
                "query": "What are the elements of a contract?",
                "context": "contract_law"
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            print("✅ Direct query working!")
            print(f"   Confidence: {data['confidence_score']}")
            print(f"   Privacy Protected: {data['privacy_protected']}")
            print(f"   Response: {data['response'][:150]}...")
        else:
            print(f"❌ Query failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Query error: {e}")

if __name__ == "__main__":
    quick_test()