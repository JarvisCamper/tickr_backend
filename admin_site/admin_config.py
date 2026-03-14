from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from decouple import config
from django.core.mail import EmailMessage, get_connection

from .models import AdminSettings


SETTING_SPECS = {
    "app_name": {"type": "str", "default": "Tickr"},
    "support_email": {"type": "str", "default": "support@tickr.com"},
    "allow_public_registration": {"type": "bool", "default": True},
    "require_email_verification": {"type": "bool", "default": False},
    "maintenance_mode": {"type": "bool", "default": False},
    "session_timeout": {"type": "int", "default": 60},
    "max_team_members": {"type": "int", "default": 20},
    "max_projects_per_user": {"type": "int", "default": 50},
    "team_invite_expiry_days": {"type": "int", "default": 7},
    "standard_daily_hours": {"type": "decimal", "default": Decimal("8.0")},
    "overtime_hourly_rate": {"type": "decimal", "default": Decimal("0.0")},
    "overtime_multiplier": {"type": "decimal", "default": Decimal("1.5")},
    "prevent_overlapping_entries": {"type": "bool", "default": True},
    "require_timer_description": {"type": "bool", "default": True},
    "invite_emails_enabled": {"type": "bool", "default": True},
    "reminder_emails_enabled": {"type": "bool", "default": False},
    "audit_log_retention_days": {"type": "int", "default": 180},
}


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _to_decimal(value: Any, default: Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def parse_admin_setting(key: str, value: Any) -> Any:
    spec = SETTING_SPECS.get(key)
    if not spec:
        return value

    default = spec["default"]
    value_type = spec["type"]

    if value_type == "bool":
        return _to_bool(value)
    if value_type == "int":
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    if value_type == "decimal":
        return _to_decimal(value, default)
    if value is None:
        return default
    return str(value)


def format_admin_setting(key: str, value: Any) -> str:
    spec = SETTING_SPECS.get(key)
    if spec and spec["type"] == "bool":
        return "true" if bool(value) else "false"
    return str(value)


def get_admin_setting(key: str) -> Any:
    spec = SETTING_SPECS.get(key)
    default = spec["default"] if spec else None
    record = AdminSettings.objects.filter(key=key).only("value").first()
    if not record:
        return default
    return parse_admin_setting(key, record.value)


def get_admin_settings() -> dict[str, Any]:
    values = {
        setting.key: parse_admin_setting(setting.key, setting.value)
        for setting in AdminSettings.objects.all()
    }

    for key, spec in SETTING_SPECS.items():
        values.setdefault(key, spec["default"])

    return values


def build_smtp_connection():
    host = config("SMTP_HOST", default="")
    from_email = config("SMTP_FROM_EMAIL", default="")
    port = config("SMTP_PORT", default=587, cast=int)
    username = config("SMTP_USERNAME", default="")
    password = config("SMTP_PASSWORD", default="")
    use_tls = config("SMTP_USE_TLS", default=True, cast=bool)
    use_ssl = config("SMTP_USE_SSL", default=False, cast=bool)

    if not host or not from_email:
        raise ValueError("SMTP settings are missing in environment variables.")

    return get_connection(
        host=host,
        port=port,
        username=username or None,
        password=password or None,
        use_tls=use_tls,
        use_ssl=use_ssl,
        fail_silently=False,
    )


def send_admin_email(subject: str, body: str, recipients: list[str]) -> None:
    connection = build_smtp_connection()
    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=config("SMTP_FROM_EMAIL", default=""),
        to=recipients,
        connection=connection,
    )
    message.send(fail_silently=False)


def send_test_email(recipient_email: str) -> None:
    settings = get_admin_settings()
    send_admin_email(
        subject=f"{settings['app_name']} SMTP test",
        body=(
            "This is a test email from the Tickr admin panel.\n\n"
            "Your SMTP settings are working."
        ),
        recipients=[recipient_email],
    )


def calculate_overtime(entries: Iterable[Any]) -> dict[int, dict[str, Any]]:
    settings = get_admin_settings()
    threshold_seconds = int(Decimal(str(settings["standard_daily_hours"])) * Decimal("3600"))
    hourly_rate = Decimal(str(settings["overtime_hourly_rate"]))
    multiplier = Decimal(str(settings["overtime_multiplier"]))

    ordered_entries = sorted(
        entries,
        key=lambda entry: (
            getattr(entry, "user_id", 0),
            getattr(entry, "start_time", None),
            getattr(entry, "id", 0),
        ),
    )

    totals: dict[tuple[int, Any], int] = {}
    result: dict[int, dict[str, Any]] = {}

    for entry in ordered_entries:
        duration = getattr(entry, "duration", None)
        if not duration or not getattr(entry, "start_time", None):
            result[entry.id] = {
                "overtime_seconds": 0,
                "overtime_hours": Decimal("0.00"),
                "overtime_pay": Decimal("0.00"),
            }
            continue

        seconds = max(int(duration.total_seconds()), 0)
        day_key = (entry.user_id, entry.start_time.date())
        used_seconds = totals.get(day_key, 0)
        regular_remaining = max(threshold_seconds - used_seconds, 0)
        overtime_seconds = max(seconds - regular_remaining, 0)
        totals[day_key] = used_seconds + seconds

        overtime_hours = (Decimal(overtime_seconds) / Decimal("3600")).quantize(Decimal("0.01"))
        overtime_pay = (overtime_hours * hourly_rate * multiplier).quantize(Decimal("0.01"))
        result[entry.id] = {
            "overtime_seconds": overtime_seconds,
            "overtime_hours": overtime_hours,
            "overtime_pay": overtime_pay,
        }

    return result
