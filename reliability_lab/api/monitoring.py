"""Metrics and reconciliation endpoints."""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from ..services import monitoring as service
from .common import api_errors, json_body


@require_GET
@api_errors
def metrics(request):
    return JsonResponse(service.metrics())


@csrf_exempt
@require_POST
@api_errors
def reconcile(request):
    json_body(request)
    return JsonResponse(service.reconcile())
