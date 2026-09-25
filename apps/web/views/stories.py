"""Motivation stories (SPEC §6.8)."""

from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from apps.content import selectors as content
from apps.content.models import Story
from apps.web.views._helpers import breadcrumbs


@require_GET
def story_list(request: HttpRequest) -> HttpResponse:
    context = {
        "stories": content.published_stories(60),
        **breadcrumbs(request, (_("Motivatsiya"), request.path)),
    }
    return render(request, "pages/stories/list.html", context)


@require_GET
def story_detail(request: HttpRequest, slug: str) -> HttpResponse:
    story = (
        Story.objects.select_related("institution", "cover_media", "article")
        .filter(slug=slug, is_published=True)
        .first()
    )
    if story is None:
        raise Http404
    others = [s for s in content.published_stories(4) if s.pk != story.pk][:3]
    context = {
        "story": story,
        "others": others,
        **breadcrumbs(request, (_("Motivatsiya"), reverse("web:story_list")), (story.title, request.path)),
    }
    return render(request, "pages/stories/detail.html", context)
