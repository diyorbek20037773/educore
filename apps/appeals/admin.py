"""Admin: appeals inbox (Murojaatlar) — workflow, assignment, replies, notes, CSV, SLA (SPEC §8)."""

from __future__ import annotations

from typing import Any

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import URLPattern, path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import StackedInline, TabularInline

from apps.appeals.models import Appeal, AppealAttachment, AppealMessage, AppealStatus
from apps.appeals.services import workflow
from apps.core.admin_base import EducoreAdmin


class AttachmentInline(TabularInline):
    model = AppealAttachment
    extra = 0
    can_delete = False
    fields = ("download", "mime_type", "size_bytes", "created_at")
    readonly_fields = fields

    def has_add_permission(self, request: HttpRequest, obj: object | None = None) -> bool:
        return False

    @admin.display(description=_("Fayl"))
    def download(self, obj: AppealAttachment) -> str:
        url = reverse("admin:appeals_appeal_attachment", args=[obj.appeal_id, obj.pk])
        return format_html('<a class="underline" href="{}">{}</a>', url, obj.original_name)


class MessageInline(StackedInline):
    model = AppealMessage
    extra = 1
    fields = ("body", "is_public", "author", "notified_at", "created_at")
    readonly_fields = ("author", "notified_at", "created_at")
    verbose_name = _("javob yoki izoh")
    verbose_name_plural = _("Yozishmalar (ochiq javob murojaatchiga e-pochta orqali yuboriladi)")


class SLAFilter(admin.SimpleListFilter):
    title = _("SLA")
    parameter_name = "sla"

    def lookups(self, request: HttpRequest, model_admin: Any) -> list[tuple[str, Any]]:
        return [("overdue", _("Muddati oʻtgan (> 15 ish kuni)"))]

    def queryset(self, request: HttpRequest, queryset: QuerySet[Appeal]) -> QuerySet[Appeal]:
        if self.value() == "overdue":
            return workflow.overdue(queryset)
        return queryset


def _status_action(status: str, label: Any) -> Any:
    def action(modeladmin: AppealAdmin, request: HttpRequest, queryset: QuerySet[Appeal]) -> None:
        changed = workflow.change_status(queryset, status)
        modeladmin.message_user(
            request, _("%(n)d ta murojaat yangilandi.") % {"n": changed}, messages.SUCCESS
        )

    action.__name__ = f"mark_{status}"
    return admin.action(description=label, permissions=["change"])(action)


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
        "is_overdue",
    )
    list_filter = (SLAFilter, "status", "priority", "topic", "institution", "assigned_to")
    list_select_related = ("institution", "assigned_to")
    search_fields = ("tracking_code", "full_name", "phone", "email", "message")
    date_hierarchy = "created_at"
    inlines = (MessageInline, AttachmentInline)
    actions = (
        "assign_to_me",
        _status_action(AppealStatus.IN_PROGRESS, _("Holat: koʻrib chiqilmoqda")),
        _status_action(AppealStatus.ANSWERED, _("Holat: javob berildi")),
        _status_action(AppealStatus.CLOSED, _("Holat: yopilgan")),
        _status_action(AppealStatus.REJECTED, _("Holat: rad etilgan")),
        "export_csv",
    )
    readonly_fields = (
        "tracking_code",
        "ip_hash",
        "user_agent",
        "locale",
        "created_at",
        "answered_at",
        "closed_at",
        "anonymized_at",
    )
    fieldsets = (
        (None, {"fields": ("tracking_code", "status", "priority", "assigned_to", "institution", "topic")}),
        (_("Murojaatchi"), {"fields": ("full_name", "phone", "email", "consent", "locale")}),
        (_("Matn"), {"fields": ("message", "internal_note")}),
        (
            _("Texnik"),
            {
                "fields": (
                    "ip_hash",
                    "user_agent",
                    "created_at",
                    "answered_at",
                    "closed_at",
                    "anonymized_at",
                )
            },
        ),
    )

    @admin.display(description=_("SLA"), boolean=True)
    def is_overdue(self, obj: Appeal) -> bool:
        if obj.status not in workflow.OPEN_STATUSES:
            return False
        cutoff = workflow.working_days_ago(workflow.SLA_WORKING_DAYS)
        return timezone.localtime(obj.created_at).date() < cutoff

    @admin.action(description=_("Menga biriktirish"), permissions=["change"])
    def assign_to_me(self, request: HttpRequest, queryset: QuerySet[Appeal]) -> None:
        count = 0
        for appeal in queryset:
            appeal.assigned_to = request.user  # type: ignore[assignment]
            if appeal.status == AppealStatus.NEW:
                workflow.apply_status(appeal, AppealStatus.IN_PROGRESS)
            appeal.save()
            count += 1
        self.message_user(
            request, _("%(n)d ta murojaat sizga biriktirildi.") % {"n": count}, messages.SUCCESS
        )

    @admin.action(description=_("CSV eksport"), permissions=["view"])
    def export_csv(self, request: HttpRequest, queryset: QuerySet[Appeal]) -> HttpResponse:
        stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
        response = HttpResponse(workflow.export_csv(queryset), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="murojaatlar-{stamp}.csv"'
        return response

    def save_model(self, request: HttpRequest, obj: Appeal, form: Any, change: bool) -> None:
        if "status" in getattr(form, "changed_data", ()):
            workflow.apply_status(obj, obj.status)
        super().save_model(request, obj, form, change)

    def save_formset(self, request: HttpRequest, form: Any, formset: Any, change: bool) -> None:
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, AppealMessage):
                if instance.author_id is None:
                    instance.author = request.user
                instance.save()
                workflow.after_message_saved(instance)
            else:
                instance.save()
        formset.save_m2m()
        for obj in formset.deleted_objects:
            obj.delete()

    def get_urls(self) -> list[URLPattern]:
        extra = [
            path(
                "<int:appeal_id>/attachments/<uuid:attachment_id>/",
                self.admin_site.admin_view(self.download_attachment),
                name="appeals_appeal_attachment",
            )
        ]
        return extra + super().get_urls()

    def download_attachment(self, request: HttpRequest, appeal_id: int, attachment_id: Any) -> FileResponse:
        """Private attachment download: staff with `appeals.view_appeal` only (SPEC §2.7)."""
        if not request.user.has_perm("appeals.view_appeal"):
            raise PermissionDenied
        attachment = get_object_or_404(AppealAttachment, pk=attachment_id, appeal_id=appeal_id)
        try:
            handle = attachment.file.open("rb")
        except FileNotFoundError as exc:
            raise Http404 from exc
        response = FileResponse(handle, as_attachment=True, filename=attachment.original_name)
        response["Content-Type"] = attachment.mime_type
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response
