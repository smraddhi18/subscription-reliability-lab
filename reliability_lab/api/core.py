"""Dashboard and process health endpoints."""

from pathlib import Path

from django.conf import settings
from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_GET

from .common import api_errors


@require_GET
@api_errors
def dashboard(request):
    path = Path(settings.BASE_DIR) / "static" / "index.html"
    return FileResponse(path.open("rb"), content_type="text/html; charset=utf-8")


@require_GET
@api_errors
def health(request):
    return JsonResponse({"status": "ok", "service": "subscription-reliability-lab"})
