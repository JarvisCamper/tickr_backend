#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def _warn_if_not_using_project_venv() -> None:
    project_root = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(project_root, "venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        running = os.path.normcase(os.path.abspath(sys.executable))
        expected = os.path.normcase(os.path.abspath(venv_python))
        if running != expected:
            sys.stderr.write(
                "\n⚠️  You're not running the project virtualenv Python.\n"
                f"    Running:  {sys.executable}\n"
                f"    Expected: {venv_python}\n"
                "    On Windows, `py` can bypass the venv. Use:\n"
                f"      & \"{venv_python}\" manage.py <command>\n\n"
            )


def main():
    """Run administrative tasks."""
    _warn_if_not_using_project_venv()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tickr.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
