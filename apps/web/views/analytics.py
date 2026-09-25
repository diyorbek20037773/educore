"""Analytics page and chart data endpoints (SPEC §6.9)."""

from __future__ import annotations

from django.core.cache import cache
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from apps.content import selectors as content
from apps.core.cache import content_version
from apps.institutions.models import MetricKey
from apps.institutions.selectors import active_institutions
from apps.web.services.charts import CHARTS, ChartParams, to_csv
from apps.web.services.home import cached, kpis
from apps.web.views._helpers import breadcrumbs

CHART_CACHE_SECONDS = 300
PERIODS = (30, 90, 365)


@require_GET
def analytics(request: HttpRequest) -> HttpResponse:
    try:
        days = int(request.GET.get("days", "30"))
    except ValueError:
        days = 30
    if days not in PERIODS:
        days = 30
    institutions = active_institutions()
    selected = [s for s in request.GET.getlist("inst") if s in {i.slug for i in institutions}]
    query = f"days={days}" + (f"&inst={','.join(selected)}" if selected else "")
    context = {
        "days": days,
        "periods": PERIODS,
        "institutions": institutions,
        "selected": selected,
        "chart_query": query,
        "metric_keys": MetricKey.choices,
        "kpis": cached("kpis", kpis),
        "admissions": content.open_admissions(),
        **breadcrumbs(request, (_("Analitika"), request.path)),
    }
    return render(request, "pages/analytics.html", context)


@require_GET
def chart_data(request: HttpRequest, chart: str) -> HttpResponse:
    builder = CHARTS.get(chart)
    if builder is None:
        raise Http404
    params = ChartParams(request.GET)
    key = f"web:chart:{chart}:{get_language()}:{content_version()}:{request.GET.urlencode()}"
    payload = cache.get(key)
    if payload is None:
        payload = builder(params)
        cache.set(key, payload, CHART_CACHE_SECONDS)
    if request.GET.get("format") == "csv":
        response = HttpResponse(to_csv(payload), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="educore-{chart}.csv"'
        return response
    return JsonResponse(payload)
