from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update one admin user and one employee user for testing."

    def handle(self, *args, **options):
        User = get_user_model()

        admin_email = "admin@tickr.com"
        admin_password = "Admin@1234"
        admin_username = "admin"

        employee_email = "employee@tickr.com"
        employee_password = "Employee@1234"
        employee_username = "employee"

        admin_user, _ = User.objects.get_or_create(
            email=admin_email,
            defaults={"username": admin_username},
        )
        admin_user.username = admin_username
        admin_user.is_active = True
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.set_password(admin_password)
        admin_user.save()

        employee_user, _ = User.objects.get_or_create(
            email=employee_email,
            defaults={"username": employee_username},
        )
        employee_user.username = employee_username
        employee_user.is_active = True
        employee_user.is_staff = False
        employee_user.is_superuser = False
        employee_user.set_password(employee_password)
        employee_user.save()

        self.stdout.write(self.style.SUCCESS("Seeded test users successfully."))
        self.stdout.write(
            f"Admin    -> email: {admin_email} | password: {admin_password}"
        )
        self.stdout.write(
            f"Employee -> email: {employee_email} | password: {employee_password}"
        )

