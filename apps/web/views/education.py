"""Programs catalogue, admissions and the students/cadets hubs (SPEC §6.5)."""

from __future__ import annotations

from typing import Any

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from apps.content import selectors as content
from apps.core.models import FAQ, FAQTopic, Page
from apps.institutions import selectors
from apps.institutions.models import InstitutionContact, ProgramForm, ProgramLevel
from apps.web.views._helpers import breadcrumbs, is_htmx, paginate


@require_GET
def program_list(request: HttpRequest) -> HttpResponse:
    level = request.GET.get("level") if request.GET.get("level") in ProgramLevel.values else None
    form = request.GET.get("form") if request.GET.get("form") in ProgramForm.values else None
    institution = request.GET.get("inst") or None
    context: dict[str, Any] = {
        "page_obj": paginate(
            request, selectors.program_list(institution_slug=institution, level=level, form=form)
        ),
        "institutions": selectors.active_institutions(),
        "levels": ProgramLevel.choices,
        "forms": ProgramForm.choices,
        "filters": {"inst": institution, "level": level, "form": form},
    }
    if is_htmx(request):
        return render(request, "partials/program_results.html", context)
    context.update(breadcrumbs(request, (_("Yoʻnalishlar"), request.path)))
    return render(request, "pages/education/program_list.html", context)


@require_GET
def program_detail(request: HttpRequest, institution: str, slug: str) -> HttpResponse:
    program = selectors.program_detail(institution, slug)
    if program is None:
        raise Http404
    related_news = list(
        content.published_articles()
        .filter(institutions=program.institution, category__slug="qabul")
        .order_by("-published_at")[:3]
    )
    context = {
        "program": program,
        "professions": list(program.professions.all()),
        "admissions": [a for a in program.admissions.all() if a.is_published],
        "related_news": related_news,
        **breadcrumbs(
            request, (_("Yoʻnalishlar"), reverse("web:program_list")), (program.name, request.path)
        ),
    }
    return render(request, "pages/education/program_detail.html", context)


@require_GET
def admissions(request: HttpRequest) -> HttpResponse:
    context = {
        "admissions": content.open_admissions(),
        "faqs": FAQ.objects.filter(is_published=True, topic=FAQTopic.QABUL, institution__isnull=True),
        "articles": content.articles_in_categories(["qabul"], 6),
        **breadcrumbs(request, (_("Qabul"), request.path)),
    }
    return render(request, "pages/education/admissions.html", context)


def _hub(request: HttpRequest, *, slug: str, category: str, topic: str, title: str) -> HttpResponse:
    context = {
        "hub_title": title,
        "intro": Page.objects.filter(slug=slug, is_published=True).first(),
        "faqs": FAQ.objects.filter(is_published=True, topic=topic).select_related("institution"),
        "articles": content.articles_in_categories([category], 9),
        "events": content.upcoming_events(4),
        "stories": content.published_stories(3),
        "contacts": InstitutionContact.objects.filter(institution__is_active=True)
        .select_related("institution")
        .order_by("institution__order", "order")[:10],
        "category_slug": category,
        **breadcrumbs(request, (title, request.path)),
    }
    return render(request, "pages/education/hub.html", context)


@require_GET
def students_hub(request: HttpRequest) -> HttpResponse:
    return _hub(request, slug="talabalar", category="talabalar", topic=FAQTopic.TALABA, title=_("Talabalar"))


@require_GET
def cadets_hub(request: HttpRequest) -> HttpResponse:
    return _hub(
        request, slug="kursantlar", category="kursantlar", topic=FAQTopic.KURSANT, title=_("Kursantlar")
    )
