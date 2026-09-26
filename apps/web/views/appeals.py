"""Appeal form, success page and tracking (SPEC §6.10)."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_http_methods
from django_ratelimit.decorators import ratelimit

from apps.appeals.forms import AppealForm, TrackForm
from apps.appeals.models import Appeal, AppealStatus
from apps.appeals.services import submission
from apps.institutions.models import InstitutionContact
from apps.web.views._helpers import breadcrumbs


def _contacts() -> list[InstitutionContact]:
    return list(
        InstitutionContact.objects.filter(institution__is_active=True)
        .select_related("institution")
        .order_by("institution__order", "order")[:10]
    )


@require_http_methods(["GET", "POST"])
def appeal_form(request: HttpRequest) -> HttpResponse:
    form = AppealForm(request.POST or None, request.FILES or None)
    status = 200
    if request.method == "POST":
        if submission.rate_limited(request, increment=False):
            form.add_error(None, _("Juda koʻp murojaat yuborildi. Iltimos, bir soatdan keyin qayta urining."))
            status = 429
        elif form.is_valid():
            if form.is_bot():
                # Honeypot: pretend success without storing anything.
                submission.rate_limited(request, increment=True)
                return redirect("web:appeal_success", code="EDC-0000-000000")
            if not submission.verify_turnstile(
                request.POST.get("cf-turnstile-response", ""), request.META.get("REMOTE_ADDR", "")
            ):
                form.add_error(
                    None, _("Xavfsizlik tekshiruvidan oʻtilmadi. Sahifani yangilab qayta urining.")
                )
            else:
                submission.rate_limited(request, increment=True)
                appeal = submission.create_appeal(_input_from(request, form))
                return redirect("web:appeal_success", code=appeal.tracking_code)
    context = {
        "form": form,
        "contacts": _contacts(),
        "turnstile_enabled": submission.turnstile_enabled(),
        **breadcrumbs(request, (_("Murojaat"), request.path)),
    }
    response = render(request, "pages/appeals/form.html", context, status=status)
    if status == 429:
        response["Retry-After"] = str(submission.RATE_LIMIT_WINDOW_SECONDS)
    return response


def _input_from(request: HttpRequest, form: AppealForm) -> submission.AppealInput:
    data = form.cleaned_data
    return submission.AppealInput(
        institution=data.get("institution"),
        topic=data["topic"],
        full_name=data["full_name"],
        phone=data["phone"],
        email=data.get("email") or "",
        message=data["message"],
        consent=bool(data["consent"]),
        locale=get_language() or "uz",
        ip=request.META.get("REMOTE_ADDR", ""),
        user_agent=request.headers.get("User-Agent", ""),
        attachment=data.get("attachment") or None,
    )


@require_GET
def appeal_success(request: HttpRequest, code: str) -> HttpResponse:
    context = {
        "code": code.upper()[:20],
        **breadcrumbs(request, (_("Murojaat"), reverse("web:appeal_form")), (_("Yuborildi"), request.path)),
    }
    return render(request, "pages/appeals/success.html", context)


@require_GET
@ratelimit(key="ip", rate="30/m", block=True)
def appeal_track(request: HttpRequest) -> HttpResponse:
    form = TrackForm(request.GET or None)
    appeal = None
    searched = False
    if form.is_valid():
        searched = True
        appeal = (
            Appeal.objects.select_related("institution")
            .filter(tracking_code=form.cleaned_data["code"])
            .first()
        )
    context = {
        "form": form,
        "appeal": appeal,
        "searched": searched,
        "timeline": _timeline(appeal) if appeal else [],
        "replies": list(appeal.messages.filter(is_public=True, author__isnull=False)) if appeal else [],
        **breadcrumbs(
            request, (_("Murojaat"), reverse("web:appeal_form")), (_("Murojaatni kuzatish"), request.path)
        ),
    }
    return render(request, "pages/appeals/track.html", context)


def _timeline(appeal: Appeal) -> list[dict[str, object]]:
    """Public status timeline: submitted → in review → answered → closed/rejected (reached steps dated)."""
    if appeal.status == AppealStatus.REJECTED:
        final = AppealStatus.REJECTED
        order = [AppealStatus.NEW, AppealStatus.IN_PROGRESS, final]
    else:
        final = AppealStatus.CLOSED
        order = [AppealStatus.NEW, AppealStatus.IN_PROGRESS, AppealStatus.ANSWERED, final]
    reached = order.index(appeal.status)
    dates = {
        AppealStatus.NEW: appeal.created_at,
        AppealStatus.ANSWERED: appeal.answered_at,
        final: appeal.closed_at,
    }
    labels = {
        AppealStatus.NEW: _("Qabul qilindi"),
        AppealStatus.IN_PROGRESS: _("Koʻrib chiqilmoqda"),
        AppealStatus.ANSWERED: _("Javob berildi"),
        AppealStatus.CLOSED: _("Yopildi"),
        AppealStatus.REJECTED: _("Rad etildi"),
    }
    return [
        {"label": labels[step], "done": index <= reached, "current": index == reached, "at": dates.get(step)}
        for index, step in enumerate(order)
    ]
