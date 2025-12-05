from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _normalize_allowed(origins):
    """Return a cleaned list of allowed origins.

    Accepts a string (comma-separated) or an iterable. Trims whitespace and
    filters out empty values. Returns a list of strings.
    """
    if not origins:
        return []
    if isinstance(origins, str):
        parts = [p.strip() for p in origins.split(",")]
    else:
        try:
            parts = [str(p).strip() for p in list(origins)]
        except Exception:
            return []
    return [p for p in parts if p]


def _is_valid_origin(origin):
    """Basic validation for an origin string (scheme + netloc)."""
    try:
        parsed = urlparse(origin)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


class EnsureCORSHeadersMiddleware(MiddlewareMixin):
    """Fallback middleware to ensure Access-Control headers are present.

    This middleware only sets headers when they are missing. It attempts to
    respect configured origins in `CORS_ALLOWED_ORIGINS` and the
    `CORS_ALLOW_ALL_ORIGINS` flag. It also sanitizes configured origins so
    invalid environment values won't accidentally produce invalid header
    values (for example a Python list repr).
    """

    def process_response(self, request, response):
        origin = request.META.get("HTTP_ORIGIN")

        # If no Origin header, nothing to do.
        if not origin:
            logger.debug("No Origin header on request %s %s", request.method, request.path)
            return response

        # If header already present, log and return
        if response.has_header("Access-Control-Allow-Origin"):
            logger.debug(
                "Response for %s %s already has CORS header: %s",
                request.method,
                request.path,
                response.get("Access-Control-Allow-Origin"),
            )
            return response

        # Determine allowed origins (normalize to list)
        try:
            allowed = getattr(settings, "CORS_ALLOWED_ORIGINS", []) or []
            allowed = _normalize_allowed(allowed)
        except Exception:
            allowed = []

        # If all origins allowed, set wildcard
        if getattr(settings, "CORS_ALLOW_ALL_ORIGINS", False):
            response["Access-Control-Allow-Origin"] = "*"
            logger.debug("Set Access-Control-Allow-Origin='*' for %s", request.path)
        else:
            # Only reflect the origin if it's explicitly allowed and looks valid
            if origin in allowed and _is_valid_origin(origin):
                response["Access-Control-Allow-Origin"] = origin
                logger.debug("Reflected Origin %s for %s", origin, request.path)
            else:
                logger.debug(
                    "Origin %s not in allowed list for %s. Allowed: %s",
                    origin,
                    request.path,
                    allowed,
                )

        # If credentials are allowed, reflect that (only for non-* origins)
        if getattr(settings, "CORS_ALLOW_CREDENTIALS", False):
            aco = response.get("Access-Control-Allow-Origin")
            if aco and aco != "*":
                response["Access-Control-Allow-Credentials"] = "true"

        # For preflight requests, echo allowed methods and headers if missing
        if request.method == "OPTIONS":
            if not response.has_header("Access-Control-Allow-Methods"):
                methods = getattr(settings, "CORS_ALLOW_METHODS", ["GET", "POST", "OPTIONS", "PUT", "PATCH", "DELETE"])
                response["Access-Control-Allow-Methods"] = ", ".join(methods)
            if not response.has_header("Access-Control-Allow-Headers"):
                headers = getattr(settings, "CORS_ALLOW_HEADERS", ["authorization", "content-type", "origin", "x-requested-with"])
                response["Access-Control-Allow-Headers"] = ", ".join(headers)

        return response
