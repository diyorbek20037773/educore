"""Editorial content: categories, tags, articles and structured objects (SPEC §2.6)."""

from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.colors import validate_hex_color
from apps.core.models import SanitizedHTMLMixin, TimeStampedModel


class Category(TimeStampedModel):
    slug = models.SlugField(_("slug"), max_length=60, unique=True)
    name = models.CharField(_("name"), max_length=120)
    description = models.TextField(_("description"), blank=True)
    icon = models.CharField(_("icon (lucide name)"), max_length=60, default="newspaper")
    color = models.CharField(_("color"), max_length=7, default="#1B3A6B", validators=[validate_hex_color])
    order = models.PositiveSmallIntegerField(_("order"), default=0)
    parent = models.ForeignKey(
        "self",
        verbose_name=_("parent"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    is_active = models.BooleanField(_("active"), default=True, db_index=True)
    show_in_nav = models.BooleanField(_("show in navigation"), default=False)

    class Meta:
        ordering = ("order", "slug")
        verbose_name = _("category")
        verbose_name_plural = _("categories")

    def __str__(self) -> str:
        return self.name


class Tag(TimeStampedModel):
    slug = models.SlugField(_("slug"), max_length=80, unique=True)
    name = models.CharField(_("name"), max_length=100)
    usage_count = models.PositiveIntegerField(_("usage count"), default=0, db_index=True)

    class Meta:
        ordering = ("-usage_count", "slug")
        verbose_name = _("tag")
        verbose_name_plural = _("tags")

    def __str__(self) -> str:
        return self.name


class ContentType(models.TextChoices):
    NEWS = "news", _("Yangilik")
    EVENT = "event", _("Tadbir")
    ADMISSION = "admission", _("Qabul")
    PROGRAM = "program", _("Yoʻnalish")
    PROFESSION = "profession", _("Kasb")
    STORY = "story", _("Hikoya")
    ANNOUNCEMENT = "announcement", _("Eʼlon")
    ANALYSIS = "analysis", _("Tahlil")
    DIGEST = "digest", _("Sharh")
    OTHER = "other", _("Boshqa")


class ArticleStatus(models.TextChoices):
    DRAFT = "draft", _("Qoralama")
    REVIEW = "review", _("Koʻrikda")
    PUBLISHED = "published", _("Eʼlon qilingan")
    ARCHIVED = "archived", _("Arxivlangan")
    REJECTED = "rejected", _("Rad etilgan")


class ArticleQuerySet(models.QuerySet["Article"]):
    def published(self) -> ArticleQuerySet:
        """Articles visible to the public."""
        return self.filter(status=ArticleStatus.PUBLISHED, published_at__lte=timezone.now())


class Article(SanitizedHTMLMixin, TimeStampedModel):
    """AI-generated or editor-written article; every AI article links its Telegram sources."""

    sanitized_fields = ("body",)

    slug = models.SlugField(_("slug"), max_length=120, unique=True)
    title = models.CharField(_("title"), max_length=200)
    lead = models.TextField(_("lead"), blank=True)
    body = models.TextField(_("body"), blank=True)
    content_type = models.CharField(
        _("content type"), max_length=14, choices=ContentType.choices, default=ContentType.NEWS, db_index=True
    )
    importance = models.PositiveSmallIntegerField(_("importance"), default=3)
    category = models.ForeignKey(
        Category, verbose_name=_("category"), on_delete=models.PROTECT, related_name="articles"
    )
    tags = models.ManyToManyField(Tag, verbose_name=_("tags"), related_name="articles", blank=True)
    primary_institution = models.ForeignKey(
        "institutions.Institution",
        verbose_name=_("primary institution"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_articles",
    )
    institutions = models.ManyToManyField(
        "institutions.Institution", verbose_name=_("institutions"), related_name="articles", blank=True
    )
    cover_media = models.ForeignKey(
        "telegram.TelegramMedia",
        verbose_name=_("cover (Telegram media)"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    cover_image = models.ImageField(
        _("cover (upload)"), upload_to="articles/covers/%Y/%m/", null=True, blank=True
    )
    status = models.CharField(
        _("status"), max_length=10, choices=ArticleStatus.choices, default=ArticleStatus.DRAFT
    )
    review_reason = models.CharField(_("review reason"), max_length=200, blank=True)
    published_at = models.DateTimeField(_("published at"), null=True, blank=True)
    source_published_at = models.DateTimeField(_("source published at"), null=True, blank=True)
    is_featured = models.BooleanField(_("featured"), default=False)
    featured_until = models.DateTimeField(_("featured until"), null=True, blank=True)
    is_pinned = models.BooleanField(_("pinned"), default=False)
    ai_generated = models.BooleanField(_("AI generated"), default=False)
    ai_confidence = models.FloatField(_("AI confidence"), null=True, blank=True)
    ai_meta = models.JSONField(_("AI metadata"), default=dict, blank=True)
    cluster = models.ForeignKey(
        "ai.EventCluster",
        verbose_name=_("cluster"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )
    view_count = models.PositiveIntegerField(_("views"), default=0)
    reading_time_min = models.PositiveSmallIntegerField(_("reading time (min)"), default=1)
    seo_title = models.CharField(_("SEO title"), max_length=70, blank=True)
    seo_description = models.CharField(_("SEO description"), max_length=170, blank=True)
    og_image = models.ImageField(_("OG image"), upload_to="articles/og/%Y/%m/", null=True, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("author"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    editor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("editor"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    edited_at = models.DateTimeField(_("edited at"), null=True, blank=True)
    needs_refresh = models.BooleanField(_("needs refresh"), default=False, db_index=True)
    translation_status = models.JSONField(_("translation status"), default=dict, blank=True)
    search_vector = SearchVectorField(null=True, editable=False)

    objects = ArticleQuerySet.as_manager()

    class Meta:
        ordering = ("-published_at", "-pk")
        verbose_name = _("article")
        verbose_name_plural = _("articles")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["status", "-published_at"], name="content_art_status_pub_idx"),
            models.Index(fields=["category", "status", "-published_at"], name="content_art_cat_idx"),
            models.Index(
                fields=["primary_institution", "status", "-published_at"], name="content_art_inst_idx"
            ),
            models.Index(fields=["is_featured", "status"], name="content_art_featured_idx"),
            GinIndex(fields=["search_vector"], name="content_art_search_gin"),
        ]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        route = (
            "web:longread_detail"
            if self.content_type in {ContentType.ANALYSIS, ContentType.DIGEST}
            else "web:news_detail"
        )
        return reverse(route, kwargs={"slug": self.slug})


class ArticleSource(TimeStampedModel):
    """Telegram post an article is based on (several when duplicates were merged)."""

    article = models.ForeignKey(
        Article, verbose_name=_("article"), on_delete=models.CASCADE, related_name="sources"
    )
    post = models.OneToOneField(
        "telegram.TelegramPost",
        verbose_name=_("post"),
        on_delete=models.PROTECT,
        related_name="article_source",
    )
    institution = models.ForeignKey(
        "institutions.Institution",
        verbose_name=_("institution"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="article_sources",
    )
    is_primary = models.BooleanField(_("primary"), default=False)
    added_at = models.DateTimeField(_("added at"), default=timezone.now)

    class Meta:
        ordering = ("-is_primary", "added_at")
        verbose_name = _("article source")
        verbose_name_plural = _("article sources")

    def __str__(self) -> str:
        return f"{self.article_id} ← {self.post}"


class ArticleMedia(TimeStampedModel):
    article = models.ForeignKey(
        Article, verbose_name=_("article"), on_delete=models.CASCADE, related_name="gallery"
    )
    media = models.ForeignKey(
        "telegram.TelegramMedia",
        verbose_name=_("Telegram media"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    image = models.ImageField(_("image (upload)"), upload_to="articles/gallery/%Y/%m/", null=True, blank=True)
    order = models.PositiveSmallIntegerField(_("order"), default=0)
    caption = models.CharField(_("caption"), max_length=300, blank=True)
    is_cover = models.BooleanField(_("cover"), default=False)

    class Meta:
        ordering = ("article", "order")
        verbose_name = _("article media")
        verbose_name_plural = _("article media")

    def __str__(self) -> str:
        return f"{self.article_id} #{self.order}"


class EventKind(models.TextChoices):
    SEMINAR = "seminar", _("Seminar")
    KONFERENSIYA = "konferensiya", _("Konferensiya")
    OCHIQ_ESHIKLAR = "ochiq_eshiklar", _("Ochiq eshiklar kuni")
    TANLOV = "tanlov", _("Tanlov")
    SPORT = "sport", _("Sport")
    MADANIY = "madaniy", _("Madaniy tadbir")
    UCHRASHUV = "uchrashuv", _("Uchrashuv")
    BOSHQA = "boshqa", _("Boshqa")


class Event(SanitizedHTMLMixin, TimeStampedModel):
    sanitized_fields = ("description",)

    slug = models.SlugField(_("slug"), max_length=140, unique=True)
    title = models.CharField(_("title"), max_length=300)
    description = models.TextField(_("description"), blank=True)
    institution = models.ForeignKey(
        "institutions.Institution",
        verbose_name=_("institution"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    article = models.ForeignKey(
        Article,
        verbose_name=_("article"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    source_post = models.ForeignKey(
        "telegram.TelegramPost",
        verbose_name=_("source post"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    starts_at = models.DateTimeField(_("starts at"), db_index=True)
    ends_at = models.DateTimeField(_("ends at"), null=True, blank=True)
    all_day = models.BooleanField(_("all day"), default=False)
    location = models.CharField(_("location"), max_length=300, blank=True)
    is_online = models.BooleanField(_("online"), default=False)
    registration_url = models.URLField(_("registration URL"), blank=True)
    kind = models.CharField(_("kind"), max_length=16, choices=EventKind.choices, default=EventKind.BOSHQA)
    cover = models.ImageField(_("cover"), upload_to="events/%Y/%m/", null=True, blank=True)
    is_published = models.BooleanField(_("published"), default=False, db_index=True)
    needs_verification = models.BooleanField(_("needs verification"), default=True)

    class Meta:
        ordering = ("starts_at",)
        verbose_name = _("event")
        verbose_name_plural = _("events")

    def __str__(self) -> str:
        return self.title

    @property
    def status(self) -> str:
        """`upcoming`, `ongoing` or `past` relative to now."""
        now = timezone.now()
        end = self.ends_at or self.starts_at
        if self.starts_at > now:
            return "upcoming"
        if end >= now:
            return "ongoing"
        return "past"

    def get_absolute_url(self) -> str:
        return reverse("web:event_detail", kwargs={"slug": self.slug})


class AdmissionStatus(models.TextChoices):
    ANNOUNCED = "announced", _("Eʼlon qilingan")
    OPEN = "open", _("Ochiq")
    CLOSED = "closed", _("Yopilgan")


class Admission(SanitizedHTMLMixin, TimeStampedModel):
    sanitized_fields = ("description", "requirements", "documents")

    institution = models.ForeignKey(
        "institutions.Institution",
        verbose_name=_("institution"),
        on_delete=models.CASCADE,
        related_name="admissions",
    )
    year = models.PositiveSmallIntegerField(_("year"))
    title = models.CharField(_("title"), max_length=300)
    description = models.TextField(_("description"), blank=True)
    starts_at = models.DateField(_("starts"), null=True, blank=True)
    ends_at = models.DateField(_("ends"), null=True, blank=True)
    programs = models.ManyToManyField(
        "institutions.Program", verbose_name=_("programs"), related_name="admissions", blank=True
    )
    requirements = models.TextField(_("requirements"), blank=True)
    documents = models.TextField(_("documents"), blank=True)
    quota = models.PositiveIntegerField(_("quota"), null=True, blank=True)
    apply_url = models.URLField(_("apply URL"), blank=True)
    contact = models.CharField(_("contact"), max_length=300, blank=True)
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=AdmissionStatus.choices,
        default=AdmissionStatus.ANNOUNCED,
        db_index=True,
    )
    source_post = models.ForeignKey(
        "telegram.TelegramPost",
        verbose_name=_("source post"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    article = models.ForeignKey(
        Article,
        verbose_name=_("article"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admissions",
    )
    is_published = models.BooleanField(_("published"), default=False, db_index=True)

    class Meta:
        ordering = ("-year", "institution__order")
        verbose_name = _("admission")
        verbose_name_plural = _("admissions")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["institution", "year", "title"], name="uniq_admission_inst_year_title"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.institution.abbreviation} {self.year}: {self.title}"


class Story(SanitizedHTMLMixin, TimeStampedModel):
    """Motivation story (motivatsiya)."""

    sanitized_fields = ("body",)

    slug = models.SlugField(_("slug"), max_length=140, unique=True)
    title = models.CharField(_("title"), max_length=300)
    person_name = models.CharField(_("person"), max_length=200)
    person_role = models.CharField(_("role"), max_length=200, blank=True)
    institution = models.ForeignKey(
        "institutions.Institution",
        verbose_name=_("institution"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stories",
    )
    quote = models.TextField(_("quote"), blank=True)
    body = models.TextField(_("body"), blank=True)
    cover = models.ImageField(_("cover"), upload_to="stories/%Y/%m/", null=True, blank=True)
    cover_media = models.ForeignKey(
        "telegram.TelegramMedia",
        verbose_name=_("cover (Telegram media)"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    article = models.ForeignKey(
        Article,
        verbose_name=_("article"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stories",
    )
    source_post = models.ForeignKey(
        "telegram.TelegramPost",
        verbose_name=_("source post"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    is_published = models.BooleanField(_("published"), default=False, db_index=True)
    published_at = models.DateTimeField(_("published at"), null=True, blank=True)
    order = models.PositiveSmallIntegerField(_("order"), default=0)

    class Meta:
        ordering = ("order", "-published_at")
        verbose_name = _("story")
        verbose_name_plural = _("stories")

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("web:story_detail", kwargs={"slug": self.slug})
