import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tickr.settings')
django.setup()

from user.serializers import LoginSerializer
from user.models import User

# Verify user
user = User.objects.filter(email='admin@admin.com').first()
print(f"✅ User found: {user.email}")
print(f"   is_staff: {user.is_staff}")
print(f"   is_superuser: {user.is_superuser}")
print(f"   Password check: {user.check_password('admin')}")

# Test serializer directly
print("\nTesting LoginSerializer...")
data = {'email': 'admin@admin.com', 'password': 'admin'}
serializer = LoginSerializer(data=data)

if serializer.is_valid():
    print("✅ Serializer is valid")
    print(f"   Validated data: {serializer.validated_data.keys()}")
    validated_user = serializer.validated_data['user']
    print(f"   User: {validated_user.email}")
    print(f"   is_staff: {validated_user.is_staff}")
else:
    print(f"❌ Serializer errors: {serializer.errors}")
