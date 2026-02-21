import logging

from django.db import DatabaseError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """Return JSON for all API exceptions, including unexpected server errors."""
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    view_name = context.get("view").__class__.__name__ if context.get("view") else "unknown"

    if isinstance(exc, DatabaseError):
        logger.exception("Database error in %s", view_name)
        return Response(
            {"detail": "Database temporarily unavailable. Please try again."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    logger.exception("Unhandled API error in %s", view_name)
    return Response(
        {"detail": "Internal server error."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
