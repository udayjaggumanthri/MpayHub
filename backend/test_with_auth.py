"""
Test API with authentication
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000/api"

def test_with_auth():
    """Test API with authentication"""
    
    print("Testing API with Authentication")
    print("=" * 60)
    
    # Step 1: Login
    print("\n1. Logging in...")
    print("   Please provide test credentials:")
    phone = input("   Phone: ").strip()
    password = input("   Password: ").strip()
    
    if not phone or not password:
        print("[ERROR] Phone and password are required")
        return False
    
    try:
        r = requests.post(
            f"{BASE_URL}/auth/login/",
            json={"phone": phone, "password": password},
            timeout=10
        )
        
        if r.status_code == 200:
            data = r.json()
            if data.get('success') and data.get('data', {}).get('tokens'):
                access_token = data['data']['tokens']['access']
                refresh_token = data['data']['tokens']['refresh']
                user = data['data'].get('user', {})
                
                print(f"[OK] Login successful")
                print(f"   User ID: {user.get('user_id', 'N/A')}")
                print(f"   Role: {user.get('role', 'N/A')}")
                
                # Step 2: Test Wallets
                print("\n2. Testing Wallets Endpoint...")
                headers = {"Authorization": f"Bearer {access_token}"}
                r = requests.get(f"{BASE_URL}/wallets/", headers=headers, timeout=10)
                
                if r.status_code == 200:
                    wallet_data = r.json()
                    print("[OK] Wallets retrieved successfully")
                    print(f"   Response: {json.dumps(wallet_data, indent=2)}")
                else:
                    print(f"[ERROR] Wallets request failed: {r.status_code}")
                    print(f"   Response: {r.text[:300]}")
                
                # Step 3: Test Current User
                print("\n3. Testing Current User Endpoint...")
                r = requests.get(f"{BASE_URL}/auth/me/", headers=headers, timeout=10)
                
                if r.status_code == 200:
                    user_data = r.json()
                    print("[OK] Current user retrieved successfully")
                    print(f"   User: {user_data.get('data', {}).get('user', {}).get('user_id', 'N/A')}")
                else:
                    print(f"[ERROR] Current user request failed: {r.status_code}")
                
                # Step 4: Test MPIN Verification
                print("\n4. Testing MPIN Verification...")
                mpin = input("   Enter MPIN (or press Enter to skip): ").strip()
                
                if mpin:
                    r = requests.post(
                        f"{BASE_URL}/auth/verify-mpin/",
                        json={"mpin": mpin},
                        headers=headers,
                        timeout=10
                    )
                    
                    if r.status_code == 200:
                        print("[OK] MPIN verified successfully")
                    else:
                        mpin_data = r.json()
                        print(f"[ERROR] MPIN verification failed: {mpin_data.get('message', 'Unknown error')}")
                else:
                    print("[SKIP] MPIN verification skipped")
                
                print("\n" + "=" * 60)
                print("[OK] Authentication Tests Completed")
                print("=" * 60)
                return True
            else:
                print(f"[ERROR] Login failed: {data.get('message', 'Unknown error')}")
                return False
        else:
            data = r.json()
            print(f"[ERROR] Login failed: {data.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_with_auth()
    sys.exit(0 if success else 1)
