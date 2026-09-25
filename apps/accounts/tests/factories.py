"""Factories for accounts."""

from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import User


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)

    email = factory.Sequence(lambda n: f"user{n}@example.uz")
    full_name = factory.Faker("name")
    password = factory.django.Password("a-long-password-123")
    is_staff = False
