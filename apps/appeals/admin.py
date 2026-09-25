"""Admin: appeals inbox (Murojaatlar) — workflow, assignment, replies, notes (SPEC §8)."""

from __future__ import annotations

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import StackedInline, TabularInline

from apps.appeals.models import Appeal, AppealAttachment, AppealMessage
from apps.core.admin_base import EducoreAdmin


class AttachmentInline(TabularInline):
    model = AppealAttachment
    extra = 0
    can_delete = False
    fields = ("original_name", "mime_type", "size_bytes", "created_at")
    readonly_fields = fields

    def has_add_permission(self, request: object, obj: object | None = None) -> bool:
        return False


class MessageInline(StackedInline):
    model = AppealMessage
    extra = 1
    fields = ("body", "is_public", "author", "notified_at")
    readonly_fields = ("author", "notified_at")


@admin.register(Appeal)
class AppealAdmin(SimpleHistoryAdmin, EducoreAdmin):
    list_display = (
        "tracking_code",
        "full_name",
        "institution",
        "topic",
        "status",
        "priority",
        "assigned_to",
        "created_at",
    )
    list_filter = ("status", "priority", "topic", "institution", "assigned_to")
    search_fields = ("tracking_code", "full_name", "phone", "email", "message")
    date_hierarchy = "created_at"
    inlines = (MessageInline, AttachmentInline)
    readonly_fields = (
        "tracking_code",
        "ip_hash",
        "user_agent",
        "locale",
        "created_at",
        "answered_at",
        "closed_at",
    )
    fieldsets = (
        (None, {"fields": ("tracking_code", "status", "priority", "assigned_to", "institution", "topic")}),
        (_("Murojaatchi"), {"fields": ("full_name", "phone", "email", "consent", "locale")}),
        (_("Matn"), {"fields": ("message", "internal_note")}),
        (_("Texnik"), {"fields": ("ip_hash", "user_agent", "created_at", "answered_at", "closed_at")}),
    )

    def save_formset(self, request: object, form: object, formset: object, change: bool) -> None:
        instances = formset.save(commit=False)  # type: ignore[attr-defined]
        for instance in instances:
            if isinstance(instance, AppealMessage) and instance.author_id is None:
                instance.author = request.user  # type: ignore[attr-defined]
            instance.save()
        formset.save_m2m()  # type: ignore[attr-defined]
        for obj in formset.deleted_objects:  # type: ignore[attr-defined]
            obj.delete()
