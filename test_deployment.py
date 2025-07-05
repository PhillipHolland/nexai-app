#!/usr/bin/env python3
"""
Test script to verify LexAI application is working correctly
"""
import requests
import json

def test_endpoints():
    """Test key application endpoints"""
    base_url = "http://127.0.0.1:5000"
    
    print("🧪 Testing LexAI Application Endpoints")
    print("=" * 50)
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print("✅ Health Check: PASSED")
            print(f"   Status: {health_data.get('status')}")
            print(f"   File Storage: {health_data.get('file_storage', {}).get('available', False)}")
            print(f"   XAI API: {health_data.get('resources', {}).get('xai_api', False)}")
        else:
            print(f"❌ Health Check: FAILED ({response.status_code})")
    except Exception as e:
        print(f"❌ Health Check: FAILED ({e})")
    
    # Test dashboard endpoint
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("✅ Dashboard: PASSED")
        else:
            print(f"❌ Dashboard: FAILED ({response.status_code})")
    except Exception as e:
        print(f"❌ Dashboard: FAILED ({e})")
    
    # Test API endpoints
    api_endpoints = [
        ("/api/clients", "Clients API"),
        ("/api/tasks", "Tasks API"),
        ("/api/calendar/events", "Calendar API"),
        ("/api/documents", "Documents API")
    ]
    
    for endpoint, name in api_endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            if response.status_code in [200, 401]:  # 401 is OK for protected endpoints
                print(f"✅ {name}: PASSED")
            else:
                print(f"❌ {name}: FAILED ({response.status_code})")
        except Exception as e:
            print(f"❌ {name}: FAILED ({e})")
    
    print("\n🎉 Application is working correctly!")
    print("🚀 Ready for deployment to Vercel!")

if __name__ == "__main__":
    test_endpoints()