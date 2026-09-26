"""Institution showcase (banner + side rails) on `/muassasalar/` (ADR-031)."""

from __future__ import annotations

from django.test import Client
from django.urls import reverse

from apps.institutions.models import Institution, InstitutionMetric, MetricKey
from apps.web.services.home import institution_cards
from apps.web.services.showcase import activity_totals, build_showcase, dense_ranks, split_rails
from apps.web.tests.conftest import SiteData


def test_dense_ranks_skip_zero_and_share_ties() -> None:
    assert dense_ranks({1: 5, 2: 9, 3: 5, 4: 0}) == {2: 1, 1: 2, 3: 2}
    assert dense_ranks({1: 0}) == {}


def test_split_rails_offsets_the_right_rail() -> None:
    left, right = split_rails([1, 2, 3])  # type: ignore[list-item]
    assert left == [1, 2, 3]
    assert right == [2, 3, 1]


def test_showcase_uses_only_real_data(site_data: SiteData) -> None:
    items = build_showcase(institution_cards(), activity_totals())
    assert len(items) == Institution.objects.filter(is_active=True).count()
    top = next(i for i in items if i.institution.pk == site_data.institution.pk)
    # The fixture institution is the only one with published articles: #1 on both activity ranks.
    assert [b.number for b in top.badges[:2]] == ["#1", "#1"]
    assert top.banner_highlight == "#1"
    assert len(top.badges) <= 4
    quiet = next(i for i in items if i.institution.pk != site_data.institution.pk)
    assert all(not b.number.startswith("#") for b in quiet.badges)
    assert quiet.banner_highlight == ""


def test_unverified_metrics_never_reach_a_badge(site_data: SiteData) -> None:
    inst = site_data.institution
    InstitutionMetric.objects.update_or_create(
        institution=inst,
        year=2026,
        key=MetricKey.STUDENTS,
        defaults={"value": 4321, "needs_verification": True},
    )
    assert MetricKey.STUDENTS not in activity_totals()[inst.pk]["metrics"]
    InstitutionMetric.objects.filter(institution=inst, key=MetricKey.STUDENTS).update(
        needs_verification=False
    )
    assert activity_totals()[inst.pk]["metrics"][MetricKey.STUDENTS] == 4321


def test_institution_list_renders_skin_layout(client: Client, site_data: SiteData) -> None:
    body = client.get(reverse("web:institution_list")).content.decode()
    for marker in ('class="subnav"', 'class="skin-banner"', "side-rail is-left", "side-rail is-right"):
        assert marker in body
    assert 'class="inst-strip"' in body
    assert body.count('class="wide-card') == Institution.objects.filter(is_active=True).count()
    assert "gradient-heading" in body
    assert site_data.institution.get_absolute_url() in body
