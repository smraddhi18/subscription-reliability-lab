"""JSON request parsing and consistent public error responses."""

import json
import logging
from functools import wraps

from django.http import JsonResponse

from ..errors import ApplicationError, DomainError, GenericException

logger = logging.getLogger(__name__)
MAX_BODY_BYTES = 1_000_000


def api_errors(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except ApplicationError as exc:
            return JsonResponse(exc.as_payload(), status=exc.status_code)
        except (json.JSONDecodeError, UnicodeDecodeError):
            error = DomainError("body must be valid JSON", error_code="invalid_json")
            return JsonResponse(error.as_payload(), status=error.status_code)
        except Exception:
            logger.exception("Unhandled request failure", extra={"path": request.path, "method": request.method})
            error = GenericException()
            return JsonResponse(error.as_payload(), status=error.status_code)
    return wrapped


def json_body(request):
    try:
        content_length = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        raise DomainError("invalid Content-Length header", error_code="invalid_content_length")
    if content_length > MAX_BODY_BYTES:
        raise DomainError("request body too large", status_code=413, error_code="payload_too_large")
    if not request.body:
        return {}
    payload = json.loads(request.body)
    if not isinstance(payload, dict):
        raise DomainError("JSON body must be an object", error_code="invalid_json_shape")
    return payload
