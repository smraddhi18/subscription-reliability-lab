"""Payment webhook HTTP endpoint."""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ..services import webhooks as service
from .common import api_errors, json_body


@csrf_exempt
@require_POST
@api_errors
def webhooks(request):
    return JsonResponse(service.receive_webhook(json_body(request)), status=202)
