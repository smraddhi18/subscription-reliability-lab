"""Subscription HTTP endpoints."""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..services import subscriptions as service
from .common import api_errors, json_body


@csrf_exempt
@require_http_methods(["GET", "POST"])
@api_errors
def subscriptions(request):
    if request.method == "GET":
        return JsonResponse({"subscriptions": service.list_subscriptions()})
    payload = json_body(request)
    result = service.create_subscription(payload.get("customer_id"), payload.get("plan"), payload.get("amount_cents"))
    return JsonResponse({"subscription": result}, status=201)
