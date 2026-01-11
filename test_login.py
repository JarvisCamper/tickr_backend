import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tickr.settings')
django.setup()

from django.test import Client
from user.models import User
import json

# Create a test client without CSRF checks
client = Client(enforce_csrf_checks=False)

# Test login
print("Testing login...")
try:
    response = client.post(
        '/api/login/',
        data=json.dumps({'email': 'admin@admin.com', 'password': 'admin'}),
        content_type='application/json'
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"\nResponse Body:")
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Content-Type: {response.get('Content-Type')}")
        print(response.content.decode())
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

# Verify user exists
user = User.objects.filter(email='admin@admin.com').first()
if user:
    print(f"\n✅ User exists:")
    print(f"   is_staff: {user.is_staff}")
    print(f"   is_superuser: {user.is_superuser}")
    print(f"   is_active: {user.is_active}")
