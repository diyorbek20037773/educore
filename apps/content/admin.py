"""Admin: editorial (Tahririyat) articles and structured content (SPEC §8)."""

from __future__ import annotations

from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from modeltranslation.admin import TranslationTabularInline
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import TabularInline

from apps.content.models import (
    Admission,
    Article,
    ArticleMedia,
    ArticleSource,
    ArticleStatus,
    Category,
    Event,
    ReviewArticle,
    Story,
    Tag,
)
from apps.core.admin_base import EducoreAdmin, TranslatedAdmin, mark_needs_verification, mark_verified


class ArticleSourceInline(TabularInline):
    model = ArticleSource
    extra = 0
    fields = ("post", "institution", "is_primary", "added_at", "original_link")
    readonly_fields = ("original_link",)
    raw_id_fields = ("post",)

    @admin.display(description=_("Asl xabar"))
    def original_link(self, obj: ArticleSource) -> str:
        if not obj.post_id:
            return "—"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>', obj.post.telegram_url, _("ochish")
        )


class ArticleMediaInline(TabularInline, TranslationTabularInline):  # type: ignore[misc]
    model = ArticleMedia
    extra = 0
    fields = ("media", "image", "order", "caption", "is_cover")
    raw_id_fields = ("media",)


@admin.register(Category)
class CategoryAdmin(TranslatedAdmin):
    list_display = ("name", "slug", "icon", "order", "is_active", "show_in_nav")
    list_editable = ("order", "is_active", "show_in_nav")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(TranslatedAdmin):
    list_display = ("name", "slug", "usage_count")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Article)
class ArticleAdmin(SimpleHistoryAdmin, TranslatedAdmin):
    list_display = (
        "title",
        "status",
        "primary_institution",
        "category",
        "content_type",
        "published_at",
        "ai_generated",
        "ai_confidence",
        "is_featured",
        "is_pinned",
    )
    list_filter = (
        "status",
        "primary_institution",
        "category",
        "content_type",
        "ai_generated",
        "needs_refresh",
        "is_featured",
    )
    search_fields = ("title", "lead", "slug")
    date_hierarchy = "published_at"
    autocomplete_fields = ("category", "primary_institution", "tags")
    filter_horizontal = ("institutions",)
    raw_id_fields = ("cover_media", "cluster", "author", "editor")
    readonly_fields = (
        "source_panel",
        "preview_link",
        "ai_meta",
        "translation_status",
        "view_count",
        "edited_at",
    )
    inlines = (ArticleSourceInline, ArticleMediaInline)
    rich_text_fields = ("body",)
    actions = (
        "publish",
        "archive",
        "send_to_review",
        "feature",
        "pin",
        "regenerate",
        "retranslate_ru",
        "retranslate_en",
        "merge_duplicates",
    )
    fieldsets = (
        (None, {"fields": ("preview_link", "title", "slug", "lead", "body")}),
        (_("Asl manba (Telegram)"), {"fields": ("source_panel",)}),
        (
            _("Tasnif"),
            {
                "fields": (
                    "status",
                    "review_reason",
                    "content_type",
                    "category",
                    "tags",
                    "importance",
                    "primary_institution",
                    "institutions",
                )
            },
        ),
        (
            _("Nashr"),
            {"fields": ("published_at", "source_published_at", "is_featured", "featured_until", "is_pinned")},
        ),
        (_("Media"), {"fields": ("cover_media", "cover_image", "og_image")}),
        (_("SEO"), {"fields": ("seo_title", "seo_description")}),
        (
            _("AI"),
            {
                "fields": (
                    "ai_generated",
                    "ai_confidence",
                    "ai_meta",
                    "cluster",
                    "needs_refresh",
                    "translation_status",
                )
            },
        ),
        (_("Muallif"), {"fields": ("author", "editor", "edited_at", "reading_time_min", "view_count")}),
    )

    def save_model(self, request: HttpRequest, obj: Article, form: object, change: bool) -> None:
        if change:
            obj.editor = request.user  # type: ignore[assignment]
            obj.edited_at = timezone.now()
        super().save_model(request, obj, form, change)  # type: ignore[arg-type]

    @admin.action(description=_("Eʼlon qilish"))
    def publish(self, request: HttpRequest, queryset: QuerySet[Article]) -> None:
        now = timezone.now()
        n = 0
        for article in queryset.exclude(status=ArticleStatus.PUBLISHED):
            article.status = ArticleStatus.PUBLISHED
            article.published_at = article.published_at or now
            article.editor = request.user  # type: ignore[assignment]
            article.save()
            n += 1
        self.message_user(request, _("%(n)d ta maqola eʼlon qilindi.") % {"n": n}, messages.SUCCESS)

    @admin.action(description=_("Arxivlash"))
    def archive(self, request: HttpRequest, queryset: QuerySet[Article]) -> None:
        n = queryset.update(status=ArticleStatus.ARCHIVED)
        self.message_user(request, _("%(n)d ta maqola arxivlandi.") % {"n": n}, messages.WARNING)

    @admin.action(description=_("Koʻrikka yuborish"))
    def send_to_review(self, request: HttpRequest, queryset: QuerySet[Article]) -> None:
        n = queryset.update(status=ArticleStatus.REVIEW, review_reason="manual")
        self.message_user(request, _("%(n)d ta maqola koʻrikka yuborildi.") % {"n": n}, messages.INFO)

    @admin.action(description=_("Tanlanganlarga qoʻshish (featured)"))
    def feature(self, request: HttpRequest, queryset: QuerySet[Article]) -> None:
        n = queryset.update(is_featured=True)
        self.message_user(request, _("%(n)d ta maqola belgilandi.") % {"n": n}, messages.SUCCESS)

    @admin.action(description=_("Qadash (pin)"))
    def pin(self, request: HttpRequest, queryset: QuerySet[Article]) -> None:
        n = queryset.update(is_pinned=True)
        self.message_user(request, _("%(n)d ta maqola qadaldi.") % {"n": n}, messages.SUCCESS)

    @admin.display(description=_("Koʻrish"))
    def preview_link(self, obj: Article) -> str:
        if not obj.pk:
            return "—"
        return format_html(
            '<a href="{}?preview=1" target="_blank" rel="noopener">{}</a>',
            obj.get_absolute_url(),
            _("Saytda koʻrish"),
        )

    @admin.display(description=_("Asl Telegram matni"))
    def source_panel(self, obj: Article) -> str:
        sources = (
            obj.sources.select_related("post__source").order_by("-is_primary", "added_at") if obj.pk else []
        )
        parts = [
            format_html(
                '<div style="margin-bottom:12px"><strong>@{}</strong> · '
                '<a href="{}" target="_blank" rel="noopener">'
                '{}</a><pre style="white-space:pre-wrap;font-size:13px;margin-top:4px">{}</pre></div>',
                s.post.source.username,
                s.post.telegram_url,
                _("ochish"),
                s.post.text,
            )
            for s in sources
        ]
        return format_html("{}", "".join(str(p) for p in parts)) if parts else "—"

    def _send(self, name: str, args: list[object]) -> None:
        from config.celery import app

        app.send_task(name, args=args, queue="ai")

    @admin.action(description=_("Qayta yaratish (AI)"))
    def regenerate(self, request: HttpRequest, queryset: QuerySet[Article]) -> None:
        for article in queryset:
            self._send("ai.regenerate_article", [article.pk])
        self.message_user(
            request, _("%(n)d ta maqola navbatga qoʻyildi.") % {"n": queryset.count()}, messages.INFO
        )

    def _retranslate(self, request: HttpRequest, queryset: QuerySet[Article], lang: str) -> None:
        n = 0
        for article in queryset.filter(status=ArticleStatus.PUBLISHED):
            self._send("ai.translate_article", [article.pk, lang])
            n += 1
        self.message_user(request, _("%(n)d ta tarjima navbatga qoʻyildi.") % {"n": n}, messages.INFO)

    @admin.action(description=_("Qayta tarjima: ruscha"))
    def retranslate_ru(self, request: HttpRequest, queryset: QuerySet[Article]) -> None:
        self._retranslate(request, queryset, "ru")

    @admin.action(description=_("Qayta tarjima: inglizcha"))
    def retranslate_en(self, request: HttpRequest, queryset: QuerySet[Article]) -> None:
        self._retranslate(request, queryset, "en")

    @admin.action(description=_("Dublikatlarni birlashtirish (eng eskisiga)"))
    def merge_duplicates(self, request: HttpRequest, queryset: QuerySet[Article]) -> None:
        from apps.content.services.editorial import merge_articles

        articles = list(queryset.order_by("source_published_at", "pk"))
        if len(articles) < 2:
            self.message_user(request, _("Kamida ikkita maqolani tanlang."), messages.WARNING)
            return
        target, *duplicates = articles
        moved = merge_articles(target, duplicates)
        self._send("ai.regenerate_article", [target.pk])
        self.message_user(
            request,
            _("%(n)d ta manba «%(t)s» maqolasiga koʻchirildi.") % {"n": moved, "t": target},
            messages.SUCCESS,
        )


@admin.register(ReviewArticle)
class ReviewQueueAdmin(ArticleAdmin):
    """The editors' landing page: everything waiting for a human decision, most important first."""

    list_display = (
        "title",
        "review_reason",
        "importance",
        "primary_institution",
        "category",
        "ai_confidence",
        "created_at",
    )
    list_filter = ("review_reason", "primary_institution", "category", "content_type")
    date_hierarchy = None

    def get_queryset(self, request: HttpRequest) -> QuerySet[Article]:
        return (
            super()
            .get_queryset(request)
            .filter(status=ArticleStatus.REVIEW)
            .order_by("-importance", "created_at")
        )


@admin.register(Event)
class EventAdmin(TranslatedAdmin):
    list_display = (
        "title",
        "institution",
        "kind",
        "starts_at",
        "is_online",
        "is_published",
        "needs_verification",
    )
    list_filter = ("institution", "kind", "is_published", "is_online", "needs_verification")
    search_fields = ("title", "location")
    date_hierarchy = "starts_at"
    autocomplete_fields = ("institution",)
    raw_id_fields = ("article", "source_post")
    prepopulated_fields = {"slug": ("title",)}
    actions = (mark_verified, mark_needs_verification)
    rich_text_fields = ("description",)


@admin.register(Admission)
class AdmissionAdmin(TranslatedAdmin):
    list_display = ("title", "institution", "year", "status", "starts_at", "ends_at", "quota", "is_published")
    list_filter = ("institution", "year", "status", "is_published")
    search_fields = ("title",)
    autocomplete_fields = ("institution",)
    filter_horizontal = ("programs",)
    raw_id_fields = ("article", "source_post")
    rich_text_fields = ("description", "requirements", "documents")


@admin.register(Story)
class StoryAdmin(TranslatedAdmin):
    list_display = ("title", "person_name", "institution", "is_published", "published_at", "order")
    list_filter = ("institution", "is_published")
    search_fields = ("title", "person_name", "quote")
    autocomplete_fields = ("institution",)
    raw_id_fields = ("article", "source_post", "cover_media")
    prepopulated_fields = {"slug": ("title",)}
    rich_text_fields = ("body",)


admin.site.register(ArticleSource, EducoreAdmin)
