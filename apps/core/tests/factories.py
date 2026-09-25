"""Factories for core models."""

from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from apps.core.models import FAQ, Page


class PageFactory(DjangoModelFactory):
    class Meta:
        model = Page

    slug = factory.Sequence(lambda n: f"sahifa-{n}")
    title = factory.Sequence(lambda n: f"Sahifa {n}")
    body = "<p>Matn</p>"


class FAQFactory(DjangoModelFactory):
    class Meta:
        model = FAQ

    question = factory.Sequence(lambda n: f"Savol {n}?")
    answer = "<p>Javob</p>"
    topic = "umumiy"
