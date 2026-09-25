"""Events: list, month calendar, detail and `.ics` download (SPEC §6.7)."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from apps.content.models import Event
from apps.institutions.selectors import active_institutions
from apps.web.views._helpers import breadcrumbs, is_htmx, paginate

WEEKDAY_LABELS = ("Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya")


def _month(value: str | None) -> date:
    today = timezone.localdate()
    try:
        year, month = (int(x) for x in (value or "").split("-"))
        return date(year, month, 1)
    except ValueError:
        return today.replace(day=1)


def _calendar(events: list[Event], month: date) -> list[list[dict[str, object]]]:
    """Weeks (Mon–Sun) of day cells with the events that start on that day."""
    by_day: dict[date, list[Event]] = defaultdict(list)
    for event in events:
        by_day[timezone.localtime(event.starts_at).date()].append(event)
    today = timezone.localdate()
    weeks = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(month.year, month.month):
        weeks.append(
            [
                {
                    "day": d,
                    "in_month": d.month == month.month,
                    "is_today": d == today,
                    "events": by_day.get(d, []),
                }
                for d in week
            ]
        )
    return weeks


@require_GET
def event_list(request: HttpRequest) -> HttpResponse:
    now = timezone.now()
    when = "past" if request.GET.get("when") == "past" else "upcoming"
    view = "calendar" if request.GET.get("view") == "calendar" else "list"
    institution = request.GET.get("inst") or None
    qs = Event.objects.filter(is_published=True).select_related("institution")
    if institution:
        qs = qs.filter(institution__slug=institution)
    context: dict[str, object] = {
        "when": when,
        "view": view,
        "institutions": active_institutions(),
        "filters": {"inst": institution},
    }
    if view == "calendar":
        month = _month(request.GET.get("month"))
        next_month = (month + timedelta(days=32)).replace(day=1)
        start = timezone.make_aware(datetime.combine(month, datetime.min.time()))
        end = timezone.make_aware(datetime.combine(next_month, datetime.min.time()))
        events = list(qs.filter(starts_at__gte=start, starts_at__lt=end).order_by("starts_at"))
        context.update(
            month=month,
            weeks=_calendar(events, month),
            weekday_labels=[_(label) for label in WEEKDAY_LABELS],
            prev_month=(month - timedelta(days=1)).replace(day=1),
            next_month=next_month,
        )
    else:
        qs = (
            qs.filter(starts_at__lt=now).order_by("-starts_at")
            if when == "past"
            else qs.filter(starts_at__gte=now).order_by("starts_at")
        )
        context["page_obj"] = paginate(request, qs, per_page=20)
    if is_htmx(request):
        return render(request, "partials/event_results.html", context)
    context.update(breadcrumbs(request, (_("Tadbirlar"), request.path)))
    return render(request, "pages/events/list.html", context)


def _get_event(slug: str) -> Event:
    event = (
        Event.objects.select_related("institution", "article").filter(slug=slug, is_published=True).first()
    )
    if event is None:
        raise Http404
    return event


@require_GET
def event_detail(request: HttpRequest, slug: str) -> HttpResponse:
    event = _get_event(slug)
    context = {
        "event": event,
        "is_past": event.starts_at < timezone.now(),
        **breadcrumbs(request, (_("Tadbirlar"), reverse("web:event_list")), (event.title, request.path)),
    }
    return render(request, "pages/events/detail.html", context)


def _ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r", "")
        .replace("\n", "\\n")
    )


def _ics_time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _fold(line: str) -> str:
    """RFC 5545 line folding at 75 octets."""
    encoded = line.encode()
    if len(encoded) <= 75:
        return line
    parts, chunk = [], b""
    for char in line:
        piece = char.encode()
        if len(chunk) + len(piece) > (75 if not parts else 74):
            parts.append(chunk.decode())
            chunk = b""
        chunk += piece
    parts.append(chunk.decode())
    return "\r\n ".join(parts)


@require_GET
def event_ics(request: HttpRequest, slug: str) -> HttpResponse:
    event = _get_event(slug)
    url = f"{settings.SITE_URL}{event.get_absolute_url()}"
    if event.all_day:
        start_day = timezone.localtime(event.starts_at).date()
        end_day = (timezone.localtime(event.ends_at).date() if event.ends_at else start_day) + timedelta(
            days=1
        )
        timing = [f"DTSTART;VALUE=DATE:{start_day:%Y%m%d}", f"DTEND;VALUE=DATE:{end_day:%Y%m%d}"]
    else:
        ends = event.ends_at or event.starts_at + timedelta(hours=2)
        timing = [f"DTSTART:{_ics_time(event.starts_at)}", f"DTEND:{_ics_time(ends)}"]
    location = event.location or (_("Onlayn") if event.is_online else "")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//EDUCORE//Events//UZ",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:event-{event.pk}@educore",
        f"DTSTAMP:{_ics_time(timezone.now())}",
        *timing,
        f"SUMMARY:{_ics_escape(event.title)}",
        f"DESCRIPTION:{_ics_escape(url)}",
        f"URL:{url}",
        *([f"LOCATION:{_ics_escape(location)}"] if location else []),
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    response = HttpResponse(
        "\r\n".join(_fold(line) for line in lines) + "\r\n", content_type="text/calendar; charset=utf-8"
    )
    response["Content-Disposition"] = f'attachment; filename="{event.slug}.ics"'
    return response
