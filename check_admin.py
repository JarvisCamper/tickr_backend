import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tickr.settings')
django.setup()

from user.models import User

# Check if admin exists
admin = User.objects.filter(email='admin@admin.com').first()

if admin:
    print(f"✅ Admin exists!")
    print(f"   Email: {admin.email}")
    print(f"   is_active: {admin.is_active}")
    print(f"   is_staff: {admin.is_staff}")
    print(f"   is_superuser: {admin.is_superuser}")
    
    # Fix if inactive
    if not admin.is_active:
        admin.is_active = True
        admin.save()
        print("   ✅ Activated user")
else:
    print("❌ Admin user not found, creating now...")
    User.objects.create_superuser('admin@admin.com', 'admin')
    print("✅ Superuser created with email: admin@admin.com, password: admin")
