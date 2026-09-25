"""Appeal form, success page and tracking (SPEC §6.10).

Phase 4 ships the UI and validation; Phase 6 adds persistence, rate limiting, Turnstile and notifications.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_http_methods

from apps.appeals.forms import AppealForm, TrackForm
from apps.appeals.models import Appeal
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
    accepted = False
    if request.method == "POST" and form.is_valid() and not form.is_bot():
        accepted = True  # Phase 6: persist, notify and redirect to `appeal_success`.
    context = {
        "form": form,
        "accepted": accepted,
        "contacts": _contacts(),
        **breadcrumbs(request, (_("Murojaat"), request.path)),
    }
    return render(request, "pages/appeals/form.html", context, status=200)


@require_GET
def appeal_success(request: HttpRequest, code: str) -> HttpResponse:
    context = {
        "code": code.upper()[:20],
        **breadcrumbs(request, (_("Murojaat"), reverse("web:appeal_form")), (_("Yuborildi"), request.path)),
    }
    return render(request, "pages/appeals/success.html", context)


@require_GET
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
        "replies": list(appeal.messages.filter(is_public=True, author__isnull=False)) if appeal else [],
        **breadcrumbs(
            request, (_("Murojaat"), reverse("web:appeal_form")), (_("Murojaatni kuzatish"), request.path)
        ),
    }
    return render(request, "pages/appeals/track.html", context)
