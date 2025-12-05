from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)


class EnsureCORSHeadersMiddleware(MiddlewareMixin):
    """Fallback middleware to ensure Access-Control headers are present.

    This middleware only sets headers when they are missing. It attempts to
    respect configured origins in `CORS_ALLOWED_ORIGINS` and the
    `CORS_ALLOW_ALL_ORIGINS` flag. It's intended as a safety-net; the
    preferred solution is to ensure `django-cors-headers` is configured and
    active.
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

        # Determine allowed origins
        try:
            allowed = getattr(settings, "CORS_ALLOWED_ORIGINS", []) or []
            if isinstance(allowed, str):
                allowed = [a.strip() for a in allowed.split(",") if a.strip()]
        except Exception:
            allowed = []

        # If all origins allowed, set wildcard
        if getattr(settings, "CORS_ALLOW_ALL_ORIGINS", False):
            response["Access-Control-Allow-Origin"] = "*"
            logger.debug("Set Access-Control-Allow-Origin='*' for %s", request.path)
        else:
            if origin in allowed:
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
            if response.get("Access-Control-Allow-Origin") and response["Access-Control-Allow-Origin"] != "*":
                response["Access-Control-Allow-Credentials"] = "true"

        # For preflight requests, echo allowed methods and headers if missing
        if request.method == "OPTIONS":
            if not response.has_header("Access-Control-Allow-Methods"):
                response["Access-Control-Allow-Methods"] = ", ".join(getattr(settings, "CORS_ALLOW_METHODS", ["GET", "POST", "OPTIONS", "PUT", "PATCH", "DELETE"]))
            if not response.has_header("Access-Control-Allow-Headers"):
                headers = getattr(settings, "CORS_ALLOW_HEADERS", ["authorization", "content-type", "origin", "x-requested-with"])
                response["Access-Control-Allow-Headers"] = ", ".join(headers)

        return response
