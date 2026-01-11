import requests
import json

url = "http://localhost:8000/api/login/"
payload = {
    "email": "admin@admin.com",
    "password": "admin"
}

print(f"Testing {url}...")
try:
    headers = {
        "Content-Type": "application/json",
        "Origin": "http://localhost:3000"
    }
    response = requests.post(url, json=payload, headers=headers)
    
    print(f"Status Code: {response.status_code}")
    print(f"\nResponse Headers:")
    for key, value in response.headers.items():
        if 'cookie' in key.lower() or key.lower() in ['content-type', 'set-cookie']:
            print(f"  {key}: {value}")
    
    print(f"\nResponse Body:")
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2))
        print(f"\n✅ Login successful!")
        print(f"   is_admin: {data.get('is_admin')}")
        print(f"   role: {data.get('role')}")
        print(f"   redirect_url: {data.get('redirect_url')}")
    else:
        print(response.text)
        
except Exception as e:
    print(f"❌ Error: {e}")
