"""
Test script to verify API integration
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000/api"

def print_response(title, response):
    """Print formatted response"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
    except:
        print(f"Response: {response.text[:500]}")
    print(f"{'='*60}\n")

def test_api_integration():
    """Test API integration"""
    
    print("Testing API Integration")
    print("=" * 60)
    
    # Test 1: Check backend is running
    print("\n1. Testing Backend Availability...")
    try:
        r = requests.get(f"{BASE_URL.replace('/api', '')}/api/docs/", timeout=5)
        if r.status_code == 200:
            print("[OK] Backend is running")
        else:
            print(f"[WARN] Backend returned status {r.status_code}")
    except Exception as e:
        print(f"[ERROR] Backend not accessible: {e}")
        return False
    
    # Test 2: Test Login (will fail without valid user, but should return proper error)
    print("\n2. Testing Login Endpoint...")
    try:
        r = requests.post(
            f"{BASE_URL}/auth/login/",
            json={"phone": "9876543210", "password": "test123"},
            timeout=10
        )
        print_response("Login Test", r)
        if r.status_code in [200, 400, 401]:
            print("[OK] Login endpoint is accessible")
        else:
            print(f"[WARN] Unexpected status: {r.status_code}")
    except Exception as e:
        print(f"[ERROR] Login test failed: {e}")
        return False
    
    # Test 3: Test BBPS Categories (requires auth, should return 401)
    print("\n3. Testing Protected Endpoint (BBPS Categories)...")
    try:
        r = requests.get(f"{BASE_URL}/bbps/categories/", timeout=10)
        print_response("BBPS Categories (No Auth)", r)
        if r.status_code == 401:
            print("[OK] Authentication is required (expected)")
        else:
            print(f"[WARN] Unexpected status: {r.status_code}")
    except Exception as e:
        print(f"[ERROR] BBPS test failed: {e}")
        return False
    
    # Test 4: Test Wallets endpoint (requires auth)
    print("\n4. Testing Wallets Endpoint...")
    try:
        r = requests.get(f"{BASE_URL}/wallets/", timeout=10)
        print_response("Wallets (No Auth)", r)
        if r.status_code == 401:
            print("[OK] Authentication is required (expected)")
        else:
            print(f"[WARN] Unexpected status: {r.status_code}")
    except Exception as e:
        print(f"[ERROR] Wallets test failed: {e}")
        return False
    
    # Test 5: Test API structure
    print("\n5. Testing API Response Format...")
    try:
        r = requests.post(
            f"{BASE_URL}/auth/login/",
            json={"phone": "invalid", "password": "invalid"},
            timeout=10
        )
        if r.status_code in [400, 401]:
            data = r.json()
            if "success" in data and "message" in data:
                print("[OK] API response format is correct")
                print(f"   - success: {data.get('success')}")
                print(f"   - message: {data.get('message')}")
            else:
                print("[WARN] API response format may be incorrect")
                print(f"   Response keys: {list(data.keys())}")
    except Exception as e:
        print(f"[ERROR] API format test failed: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("[OK] Basic API Integration Tests Completed")
    print("=" * 60)
    print("\nNext Steps:")
    print("   1. Create a test user via Django admin or API")
    print("   2. Test login with valid credentials")
    print("   3. Test authenticated endpoints")
    print("   4. Test frontend connection")
    
    return True

if __name__ == "__main__":
    success = test_api_integration()
    sys.exit(0 if success else 1)
