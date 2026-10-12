"""Detection, evidence and incident analysis endpoints."""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .. import detection, incident_analysis
from ..errors import DomainError
from .common import api_errors, json_body


@require_GET
@api_errors
def anomalies(request):
    return JsonResponse(detection.detect())


@require_GET
@api_errors
def incidents(request):
    return JsonResponse({"incidents": detection.incident_list()})


@require_GET
@api_errors
def evidence(request, evidence_id):
    item = detection.get_evidence(evidence_id)
    return JsonResponse(item or {"error": "evidence not found"}, status=200 if item else 404)


@csrf_exempt
@require_POST
@api_errors
def analyze_incident(request):
    payload = json_body(request)
    incident_id = payload.get("incident_id")
    if incident_id is not None and not isinstance(incident_id, str):
        raise DomainError("incident_id must be a string")
    result = incident_analysis.analyze(incident_id)
    return JsonResponse(result, status=200 if "error" not in result else 404)
