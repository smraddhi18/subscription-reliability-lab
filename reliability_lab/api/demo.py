"""Synthetic scenario endpoints."""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .. import detection
from ..services import demo as service
from .common import api_errors, json_body


@csrf_exempt
@require_POST
@api_errors
def demo_seed(request):
    json_body(request)
    return JsonResponse(service.seed_demo())


@csrf_exempt
@require_POST
@api_errors
def demo_payment_spike(request):
    json_body(request)
    result = service.inject_payment_spike()
    result["detection"] = detection.detect()
    return JsonResponse(result, status=201)


@csrf_exempt
@require_POST
@api_errors
def demo_payment_failed(request):
    json_body(request)
    return JsonResponse(service.inject_payment_failure(), status=201)


@csrf_exempt
@require_POST
@api_errors
def demo_duplicate_webhook(request):
    json_body(request)
    return JsonResponse(service.inject_duplicate_webhook(), status=201)
