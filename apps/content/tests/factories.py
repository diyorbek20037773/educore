"""Factories for editorial content."""

from __future__ import annotations

from datetime import timedelta

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.content.models import (
    Admission,
    Article,
    ArticleMedia,
    ArticleSource,
    Category,
    Event,
    Story,
    Tag,
)
from apps.institutions.tests.factories import InstitutionFactory
from apps.telegram.tests.factories import TelegramPostFactory


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
        django_get_or_create = ("slug",)

    slug = factory.Sequence(lambda n: f"kategoriya-{n}")
    name = factory.Sequence(lambda n: f"Kategoriya {n}")


class TagFactory(DjangoModelFactory):
    class Meta:
        model = Tag
        django_get_or_create = ("slug",)

    slug = factory.Sequence(lambda n: f"teg-{n}")
    name = factory.Sequence(lambda n: f"Teg {n}")


class ArticleFactory(DjangoModelFactory):
    class Meta:
        model = Article
        skip_postgeneration_save = True

    slug = factory.Sequence(lambda n: f"maqola-{n}-abc123")
    title = factory.Sequence(lambda n: f"Maqola sarlavhasi {n}")
    lead = "Qisqacha kirish matni."
    body = "<p>Maqola matni.</p>"
    category = factory.SubFactory(CategoryFactory)
    primary_institution = factory.SubFactory(InstitutionFactory)
    status = "published"
    published_at = factory.LazyFunction(lambda: timezone.now() - timedelta(minutes=5))

    class Params:
        draft = factory.Trait(status="draft", published_at=None)
        review = factory.Trait(status="review", published_at=None, review_reason="confidence")

    @factory.post_generation
    def institutions_m2m(self, create: bool, extracted: object, **kwargs: object) -> None:
        if create and self.primary_institution_id:
            self.institutions.add(self.primary_institution)


class ArticleSourceFactory(DjangoModelFactory):
    class Meta:
        model = ArticleSource

    article = factory.SubFactory(ArticleFactory)
    post = factory.SubFactory(TelegramPostFactory)
    institution = factory.LazyAttribute(lambda o: o.post.source.institution)
    is_primary = True


class ArticleMediaFactory(DjangoModelFactory):
    class Meta:
        model = ArticleMedia

    article = factory.SubFactory(ArticleFactory)
    order = 0


class EventFactory(DjangoModelFactory):
    class Meta:
        model = Event

    slug = factory.Sequence(lambda n: f"tadbir-{n}")
    title = factory.Sequence(lambda n: f"Tadbir {n}")
    institution = factory.SubFactory(InstitutionFactory)
    starts_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=3))
    kind = "seminar"
    location = "Toshkent"
    is_published = True


class AdmissionFactory(DjangoModelFactory):
    class Meta:
        model = Admission

    institution = factory.SubFactory(InstitutionFactory)
    year = 2026
    title = factory.Sequence(lambda n: f"Qabul eʼloni {n}")
    status = "open"
    starts_at = factory.LazyFunction(lambda: timezone.localdate() - timedelta(days=1))
    ends_at = factory.LazyFunction(lambda: timezone.localdate() + timedelta(days=30))
    is_published = True


class StoryFactory(DjangoModelFactory):
    class Meta:
        model = Story

    slug = factory.Sequence(lambda n: f"hikoya-{n}")
    title = factory.Sequence(lambda n: f"Hikoya {n}")
    person_name = factory.Faker("name")
    institution = factory.SubFactory(InstitutionFactory)
    quote = "Maqsad sari intilish — muvaffaqiyat kaliti."
    is_published = True
    published_at = factory.LazyFunction(timezone.now)
