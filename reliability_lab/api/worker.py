"""Retry worker control endpoints."""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ..errors import DomainError
from ..services import worker as service
from .common import api_errors, json_body


@csrf_exempt
@require_POST
@api_errors
def worker_run(request):
    if request.GET.get("recover", "").lower() == "true":
        return JsonResponse(service.recover_processing_jobs())
    payload = json_body(request)
    limit = payload.get("limit", 20)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise DomainError("limit must be an integer from 1 to 100", error_code="invalid_limit")
    return JsonResponse(service.run_worker(limit=limit, force_failure=bool(payload.get("force_failure", False)), ignore_backoff=bool(payload.get("ignore_backoff", False))))


@csrf_exempt
@require_POST
@api_errors
def worker_crash(request):
    json_body(request)
    return JsonResponse(service.simulate_worker_crash())
