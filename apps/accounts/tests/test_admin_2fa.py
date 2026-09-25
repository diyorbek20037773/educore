"""Admin access and mandatory 2FA (SPEC §2.2, AC1.2)."""

from __future__ import annotations

from base64 import b32decode

import pytest
from django.conf import settings
from django.contrib import admin
from django.test import Client
from django.urls import reverse
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.accounts.models import User
from apps.core.services.seeding import seed_reference_data

pytestmark = pytest.mark.django_db
ADMIN = f"/{settings.ADMIN_URL_PATH}/"


def _staff(**extra: object) -> User:
    return User.objects.create_user(
        email="editor@example.uz", password="a-long-password-123", is_staff=True, **extra
    )


def _verified_client(user: User) -> Client:
    device = TOTPDevice.objects.create(user=user, name="default", confirmed=True)
    client = Client()
    client.force_login(user)
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()
    return client


def test_anonymous_admin_goes_to_two_factor_login(client: Client) -> None:
    response = client.get(ADMIN, follow=True)
    assert response.redirect_chain[-1][0].startswith(reverse("two_factor:login"))
    assert response.status_code == 200


def test_staff_without_device_is_sent_to_setup(client: Client) -> None:
    client.force_login(_staff())
    response = client.get(ADMIN)
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("two_factor:setup"))


def test_staff_with_unverified_device_is_sent_to_login(client: Client) -> None:
    user = _staff()
    TOTPDevice.objects.create(user=user, name="default", confirmed=True)
    client.force_login(user)
    response = client.get(ADMIN)
    assert response["Location"].startswith(reverse("two_factor:login"))


def test_non_admin_pages_are_not_intercepted(client: Client) -> None:
    client.force_login(_staff())
    assert client.get("/").status_code == 200


def test_two_factor_setup_wizard_confirms_a_totp_device(client: Client) -> None:
    user = _staff()
    client.force_login(user)
    setup = reverse("two_factor:setup")
    assert client.get(setup).status_code == 200
    response = client.post(setup, {"setup_view-current_step": "welcome"})
    assert response.status_code == 200
    # Only the TOTP generator is enabled, so the wizard skips the "method" step.
    token = totp(b32decode(client.session["django_two_factor-qr_secret_key"]))
    response = client.post(setup, {"setup_view-current_step": "generator", "generator-token": token})
    assert TOTPDevice.objects.filter(user=user, confirmed=True).exists(), response.content[:500]


def test_verified_superuser_sees_dashboard_and_every_model(client: Client) -> None:
    seed_reference_data()
    user = User.objects.create_superuser(email="owner@example.uz", password="a-long-password-123")
    verified = _verified_client(user)
    index = verified.get(ADMIN)
    assert index.status_code == 200
    assert b"Bugun kelgan postlar" in index.content
    failures = []
    for model in admin.site._registry:
        opts = model._meta
        url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")
        status = verified.get(url).status_code
        if status != 200:
            failures.append((url, status))
    assert not failures


def test_admin_csp_is_relaxed_only_for_admin(client: Client) -> None:
    public = client.get("/")
    admin_login = client.get(reverse("two_factor:login"))
    assert "unsafe-eval" not in public["Content-Security-Policy"]
    assert "unsafe-eval" in admin_login["Content-Security-Policy"]
