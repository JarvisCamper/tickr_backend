from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class EnsureCORSHeadersMiddleware(MiddlewareMixin):
    """Fallback middleware to ensure Access-Control headers are present.

    This middleware only sets headers when they are missing. It attempts to
    respect configured origins in `CORS_ALLOWED_ORIGINS` and the
    `CORS_ALLOW_ALL_ORIGINS` flag. It's intended as a safety-net; the
    preferred solution is to ensure `django-cors-headers` is configured and
    active.
    """

    def process_response(self, request, response):
        # If response already has the header, do nothing.
        if response.has_header("Access-Control-Allow-Origin"):
            return response

        origin = request.META.get("HTTP_ORIGIN")

        # If no origin on request, nothing to do.
        if not origin:
            return response

        # If all origins allowed, set wildcard
        if getattr(settings, "CORS_ALLOW_ALL_ORIGINS", False):
            response["Access-Control-Allow-Origin"] = "*"
        else:
            allowed = getattr(settings, "CORS_ALLOWED_ORIGINS", []) or []
            # Accept both list and comma-separated string defensively
            if isinstance(allowed, str):
                allowed = [a.strip() for a in allowed.split(",") if a.strip()]

            if origin in allowed:
                response["Access-Control-Allow-Origin"] = origin

        # If credentials are allowed, reflect that
        if getattr(settings, "CORS_ALLOW_CREDENTIALS", False):
            # Browsers disallow '*' with credentials, ensure a specific origin
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
