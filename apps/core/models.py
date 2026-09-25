"""Core models: shared abstract base, site settings singleton, static pages and FAQ (SPEC §2.1)."""

from __future__ import annotations

from typing import ClassVar

from django.core.cache import cache
from django.db import models
from django.utils.translation import gettext_lazy as _

SITE_SETTING_CACHE_KEY = "core:site_setting"
SITE_SETTING_CACHE_SECONDS = 60


class TimeStampedModel(models.Model):
    """Abstract base adding ``created_at`` / ``updated_at`` to every concrete model."""

    created_at = models.DateTimeField(_("created at"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        abstract = True


class SanitizedHTMLMixin(models.Model):
    """Sanitize rich-text fields (and their `_uz/_uz_cyrl/_ru/_en` variants) on every save (SPEC §2)."""

    sanitized_fields: ClassVar[tuple[str, ...]] = ()

    class Meta:
        abstract = True

    def save(self, *args: object, **kwargs: object) -> None:
        from apps.core.sanitize import sanitize_html

        for base in self.sanitized_fields:
            for suffix in ("", "_uz", "_uz_cyrl", "_ru", "_en"):
                name = f"{base}{suffix}"
                value = getattr(self, name, None)
                if isinstance(value, str) and value:
                    setattr(self, name, sanitize_html(value))
        super().save(*args, **kwargs)  # type: ignore[arg-type]


class PublishMode(models.TextChoices):
    AUTO = "auto", _("Avtomatik")
    REVIEW = "review", _("Tahririyat koʻrigi")
    OFF = "off", _("Oʻchirilgan")


class OnSourceDelete(models.TextChoices):
    ARCHIVE = "archive", _("Arxivlash")
    KEEP = "keep", _("Saqlab qolish")


class SiteSetting(TimeStampedModel):
    """Singleton with runtime settings. Blank/null values fall back to env defaults (`get_setting`)."""

    site_name = models.CharField(_("site name"), max_length=100, default="EDUCORE")
    tagline = models.CharField(_("tagline"), max_length=255, blank=True)
    publish_mode = models.CharField(
        _("publish mode"), max_length=10, choices=PublishMode.choices, blank=True, default=""
    )
    publish_confidence_threshold = models.FloatField(_("publish confidence threshold"), null=True, blank=True)
    on_source_delete = models.CharField(
        _("on source delete"), max_length=10, choices=OnSourceDelete.choices, blank=True, default=""
    )
    ai_daily_usd_budget = models.DecimalField(
        _("AI daily budget (USD)"), max_digits=8, decimal_places=2, null=True, blank=True
    )
    ai_translate_to = models.JSONField(_("AI translation languages"), null=True, blank=True)
    live_panel_refresh_seconds = models.PositiveIntegerField(_("live panel refresh (s)"), default=30)
    maintenance_mode = models.BooleanField(_("maintenance mode"), default=False)
    contact_email = models.EmailField(_("contact e-mail"), blank=True)
    contact_phone = models.CharField(_("contact phone"), max_length=32, blank=True)
    address = models.CharField(_("address"), max_length=255, blank=True)
    footer_text = models.TextField(_("footer text"), blank=True)
    social_links = models.JSONField(_("social links"), default=dict, blank=True)
    ga_measurement_id = models.CharField(_("GA measurement id"), max_length=32, blank=True)

    class Meta:
        ordering = ("pk",)
        verbose_name = _("site settings")
        verbose_name_plural = _("site settings")

    def __str__(self) -> str:
        return str(_("Site settings"))

    def save(self, *args: object, **kwargs: object) -> None:
        self.pk = 1
        super().save(*args, **kwargs)  # type: ignore[arg-type]
        cache.delete(SITE_SETTING_CACHE_KEY)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        """The singleton cannot be deleted."""
        return 0, {}

    @classmethod
    def get(cls) -> SiteSetting:
        """Return the singleton (cached 60 s), creating it with defaults on first access."""
        cached = cache.get(SITE_SETTING_CACHE_KEY)
        if isinstance(cached, SiteSetting):
            return cached
        obj, _created = cls.objects.get_or_create(pk=1)
        cache.set(SITE_SETTING_CACHE_KEY, obj, SITE_SETTING_CACHE_SECONDS)
        return obj


class Page(SanitizedHTMLMixin, TimeStampedModel):
    """Static page (about, contacts, privacy, terms, hub intros)."""

    sanitized_fields = ("body",)

    slug = models.SlugField(_("slug"), max_length=120, unique=True)
    title = models.CharField(_("title"), max_length=200)
    body = models.TextField(_("body"), blank=True)
    is_published = models.BooleanField(_("published"), default=True, db_index=True)
    show_in_footer = models.BooleanField(_("show in footer"), default=False)
    order = models.PositiveSmallIntegerField(_("order"), default=0)
    seo_title = models.CharField(_("SEO title"), max_length=70, blank=True)
    seo_description = models.CharField(_("SEO description"), max_length=170, blank=True)

    class Meta:
        ordering = ("order", "slug")
        verbose_name = _("page")
        verbose_name_plural = _("pages")

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        from django.urls import NoReverseMatch, reverse

        names = {
            "biz-haqimizda": "about",
            "aloqa": "contact",
            "maxfiylik-siyosati": "privacy",
            "foydalanish-shartlari": "terms",
            "talabalar": "students_hub",
            "kursantlar": "cadets_hub",
        }
        try:
            return reverse(f"web:{names[self.slug]}") if self.slug in names else f"/{self.slug}/"
        except NoReverseMatch:
            return f"/{self.slug}/"


class FAQTopic(models.TextChoices):
    QABUL = "qabul", _("Qabul")
    TALIM = "talim", _("Taʼlim")
    KURSANT = "kursant", _("Kursantlar")
    TALABA = "talaba", _("Talabalar")
    KASB = "kasb", _("Kasblar")
    MUROJAAT = "murojaat", _("Murojaat")
    UMUMIY = "umumiy", _("Umumiy")


class FAQ(SanitizedHTMLMixin, TimeStampedModel):
    """Frequently asked question, optionally scoped to an institution."""

    sanitized_fields = ("answer",)

    question = models.CharField(_("question"), max_length=300)
    answer = models.TextField(_("answer"))
    topic = models.CharField(_("topic"), max_length=20, choices=FAQTopic.choices, default=FAQTopic.UMUMIY)
    institution = models.ForeignKey(
        "institutions.Institution",
        verbose_name=_("institution"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="faqs",
    )
    order = models.PositiveSmallIntegerField(_("order"), default=0)
    is_published = models.BooleanField(_("published"), default=True)

    class Meta:
        ordering = ("topic", "order", "pk")
        verbose_name = _("FAQ")
        verbose_name_plural = _("FAQ")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["topic", "is_published"], name="core_faq_topic_pub_idx"),
        ]

    def __str__(self) -> str:
        return self.question
