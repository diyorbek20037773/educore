"""Appeals (Murojaat): public submissions, private attachments, replies (SPEC §2.7)."""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils.functional import LazyObject
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class PrivateStorage(LazyObject):
    """Filesystem storage under `PRIVATE_ROOT` — never under MEDIA_ROOT, never served by Caddy."""

    def _setup(self) -> None:
        self._wrapped = FileSystemStorage(location=settings.PRIVATE_ROOT, base_url=None)


private_storage = PrivateStorage()


def get_private_storage() -> PrivateStorage:
    """Callable storage: migrations reference this function, not an environment-specific path."""
    return private_storage


class AppealTopic(models.TextChoices):
    QABUL = "qabul", _("Qabul")
    TALIM = "talim", _("Taʼlim jarayoni")
    KURSANT_TALABA = "kursant_talaba", _("Kursant va talabalar")
    SHIKOYAT = "shikoyat", _("Shikoyat")
    TAKLIF = "taklif", _("Taklif")
    HAMKORLIK = "hamkorlik", _("Hamkorlik")
    BOSHQA = "boshqa", _("Boshqa")


class AppealStatus(models.TextChoices):
    NEW = "new", _("Yangi")
    IN_PROGRESS = "in_progress", _("Koʻrib chiqilmoqda")
    ANSWERED = "answered", _("Javob berildi")
    CLOSED = "closed", _("Yopilgan")
    REJECTED = "rejected", _("Rad etilgan")


class AppealPriority(models.TextChoices):
    NORMAL = "normal", _("Oddiy")
    HIGH = "high", _("Yuqori")


class Appeal(TimeStampedModel):
    tracking_code = models.CharField(_("tracking code"), max_length=20, unique=True)
    institution = models.ForeignKey(
        "institutions.Institution",
        verbose_name=_("institution"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appeals",
    )
    topic = models.CharField(_("topic"), max_length=16, choices=AppealTopic.choices)
    full_name = models.CharField(_("full name"), max_length=200)
    phone = models.CharField(_("phone"), max_length=20)
    email = models.EmailField(_("e-mail"), blank=True)
    message = models.TextField(_("message"))
    consent = models.BooleanField(_("consent to data processing"), default=False)
    status = models.CharField(
        _("status"), max_length=12, choices=AppealStatus.choices, default=AppealStatus.NEW, db_index=True
    )
    priority = models.CharField(
        _("priority"), max_length=8, choices=AppealPriority.choices, default=AppealPriority.NORMAL
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("assigned to"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    ip_hash = models.CharField(_("IP hash"), max_length=64, blank=True)
    user_agent = models.CharField(_("user agent"), max_length=300, blank=True)
    locale = models.CharField(_("language"), max_length=10, default="uz")
    answered_at = models.DateTimeField(_("answered at"), null=True, blank=True)
    closed_at = models.DateTimeField(_("closed at"), null=True, blank=True)
    internal_note = models.TextField(_("internal note"), blank=True)
    anonymized_at = models.DateTimeField(_("anonymized at"), null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("appeal")
        verbose_name_plural = _("appeals")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["status", "created_at"], name="appeal_status_created_idx"),
        ]

    def __str__(self) -> str:
        return self.tracking_code


def attachment_upload_to(instance: AppealAttachment, filename: str) -> str:
    """Opaque random name; the original name is kept in `original_name` only."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"appeals/{uuid.uuid4().hex[:2]}/{uuid.uuid4().hex}.{ext}"


class AppealAttachment(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appeal = models.ForeignKey(
        Appeal, verbose_name=_("appeal"), on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(
        _("file"), storage=get_private_storage, upload_to=attachment_upload_to, max_length=200
    )
    original_name = models.CharField(_("original name"), max_length=255)
    size_bytes = models.PositiveIntegerField(_("size (bytes)"))
    mime_type = models.CharField(_("MIME type"), max_length=100)

    class Meta:
        ordering = ("created_at",)
        verbose_name = _("appeal attachment")
        verbose_name_plural = _("appeal attachments")

    def __str__(self) -> str:
        return self.original_name


class AppealMessage(TimeStampedModel):
    """Reply or note on an appeal; `author=None` means the applicant."""

    appeal = models.ForeignKey(
        Appeal, verbose_name=_("appeal"), on_delete=models.CASCADE, related_name="messages"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("author"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    body = models.TextField(_("text"))
    is_public = models.BooleanField(_("visible to applicant"), default=True)
    notified_at = models.DateTimeField(_("notified at"), null=True, blank=True)

    class Meta:
        ordering = ("created_at",)
        verbose_name = _("appeal message")
        verbose_name_plural = _("appeal messages")

    def __str__(self) -> str:
        return f"{self.appeal.tracking_code} message {self.pk}"
