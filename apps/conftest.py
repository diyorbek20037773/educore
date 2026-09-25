"""Project-wide pytest fixtures."""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.accounts.models import User


@pytest.fixture
def admin_user(db: Any) -> User:
    return User.objects.create_superuser(email="owner@example.uz", password="a-long-password-123")


@pytest.fixture
def verified_admin_client(admin_user: User) -> Client:
    """A superuser session that already passed TOTP verification (admin is 2FA-only)."""
    device = TOTPDevice.objects.create(user=admin_user, name="default", confirmed=True)
    client = Client()
    client.force_login(admin_user)
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()
    return client
