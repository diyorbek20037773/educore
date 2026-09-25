"""`seed_all` is create-only and idempotent (SPEC §12, AC1.1)."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db.models import Count
from django_celery_beat.models import PeriodicTask

from apps.content.models import Category
from apps.core.models import FAQ, SiteSetting
from apps.core.services.seeding import placeholder_logo_svg, seed_reference_data
from apps.institutions.models import Institution, Profession, Program
from apps.telegram.models import TelegramSource

pytestmark = pytest.mark.django_db


def test_seed_counts_meet_spec() -> None:
    seed_reference_data()
    assert Institution.objects.count() == 5
    assert Category.objects.count() == 16
    assert Profession.objects.count() >= 20
    assert FAQ.objects.count() >= 15
    assert TelegramSource.objects.count() == 5
    per_institution = (
        Program.objects.order_by().values("institution").annotate(n=Count("id")).values_list("n", flat=True)
    )
    assert len(per_institution) == 5
    assert min(per_institution) >= 4
    assert Program.objects.values("level").distinct().count() >= 4


def test_seed_is_idempotent_and_create_only() -> None:
    seed_reference_data()
    inst = Institution.objects.get(slug="iiv-akademiyasi")
    inst.full_name = "Owner edited name"
    inst.save()

    second = seed_reference_data()

    assert sum(second.created.values()) == 0
    inst.refresh_from_db()
    assert inst.full_name == "Owner edited name"
    assert Institution.objects.count() == 5


def test_seed_flags_everything_for_verification() -> None:
    seed_reference_data()
    assert not Institution.objects.filter(needs_verification=False).exists()
    assert not Program.objects.filter(needs_verification=False).exists()
    assert not Profession.objects.filter(needs_verification=False).exists()


def test_seed_sources_are_lowercase_and_linked() -> None:
    seed_reference_data()
    usernames = set(TelegramSource.objects.values_list("username", flat=True))
    assert "dbq_bojxona_instituti" in usernames
    assert all(u == u.lower() for u in usernames)
    assert not TelegramSource.objects.filter(institution__isnull=True).exists()


def test_seed_all_command_syncs_roles_and_beat() -> None:
    call_command("seed_all")
    call_command("seed_all")
    assert set(Group.objects.values_list("name", flat=True)) >= {"admin", "editor", "moderator", "analyst"}
    assert Group.objects.get(name="moderator").permissions.filter(codename="view_appeal").exists()
    assert not Group.objects.get(name="analyst").permissions.filter(codename__startswith="change_").exists()
    assert PeriodicTask.objects.filter(name="telegram.relay_outbox").count() == 1
    assert SiteSetting.objects.count() == 1


def test_placeholder_logo_escapes_and_colors() -> None:
    svg = placeholder_logo_svg("A<B", "#123456")
    assert "A&lt;B" in svg
    assert 'fill="#123456"' in svg
