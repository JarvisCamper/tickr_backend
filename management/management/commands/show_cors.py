from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Print parsed CORS settings for debugging"

    def handle(self, *args, **options):
        allowed = getattr(settings, "CORS_ALLOWED_ORIGINS", []) or []
        # Normalize for display
        if isinstance(allowed, str):
            allowed_list = [a.strip() for a in allowed.split(",") if a.strip()]
        else:
            try:
                allowed_list = [str(a).strip() for a in list(allowed)]
            except Exception:
                allowed_list = []

        self.stdout.write("CORS debug information:\n")
        self.stdout.write(f"CORS_ALLOW_ALL_ORIGINS: {getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False)}")
        self.stdout.write(f"CORS_ALLOW_CREDENTIALS: {getattr(settings, 'CORS_ALLOW_CREDENTIALS', False)}")
        self.stdout.write("CORS_ALLOWED_ORIGINS (parsed):")
        for o in allowed_list:
            self.stdout.write(f" - {o}")
        self.stdout.write("\nCSRF_TRUSTED_ORIGINS (parsed):")
        csrf = getattr(settings, "CSRF_TRUSTED_ORIGINS", []) or []
        if isinstance(csrf, str):
            csrf_list = [a.strip() for a in csrf.split(",") if a.strip()]
        else:
            try:
                csrf_list = [str(a).strip() for a in list(csrf)]
            except Exception:
                csrf_list = []
        for o in csrf_list:
            self.stdout.write(f" - {o}")
