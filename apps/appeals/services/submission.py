"""Appeal submission shared by the public form and `POST /api/v1/appeals` (SPEC §6.10, §9).

One service validates attachments (size, extension, sniffed MIME), checks Turnstile, enforces the shared
5/hour/IP limit and persists the appeal + attachment atomically; notifications run after commit.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import zipfile
from dataclasses import dataclass
from typing import Any

import httpx
import magic
import structlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, transaction
from django.http import HttpRequest
from django.utils import timezone
from django.utils.translation import gettext as _
from django_ratelimit.core import get_usage

from apps.appeals.models import Appeal, AppealAttachment
from apps.institutions.models import Institution

log = structlog.get_logger(__name__)

MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
# extension -> MIME types libmagic may report for a genuine file of that kind
ALLOWED_ATTACHMENTS: dict[str, tuple[str, ...]] = {
    "pdf": ("application/pdf",),
    "jpg": ("image/jpeg",),
    "jpeg": ("image/jpeg",),
    "png": ("image/png",),
    "docx": (DOCX_MIME, "application/zip"),
}
RATE_LIMIT_GROUP = "appeals.submit"
RATE_LIMIT = "5/h"
RATE_LIMIT_WINDOW_SECONDS = 3600
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TRACKING_PREFIX = "EDC"


@dataclass(frozen=True, slots=True)
class AppealInput:
    """Validated applicant data (form or API) plus request metadata."""

    topic: str
    full_name: str
    phone: str
    message: str
    consent: bool
    institution: Institution | None = None
    email: str = ""
    locale: str = "uz"
    ip: str = ""
    user_agent: str = ""
    attachment: UploadedFile | None = None


@dataclass(frozen=True, slots=True)
class CheckedAttachment:
    upload: UploadedFile
    extension: str
    mime_type: str


def validate_attachment(upload: UploadedFile) -> CheckedAttachment:
    """Reject files over 5 MB, with a foreign extension, or whose sniffed content does not match it."""
    if upload.size is None or upload.size > MAX_ATTACHMENT_BYTES:
        raise ValidationError(_("Fayl hajmi 5 MB dan oshmasligi kerak."), code="too_large")
    name = upload.name or ""
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    allowed = ALLOWED_ATTACHMENTS.get(extension)
    invalid = ValidationError(_("Faqat PDF, JPG, PNG yoki DOCX fayllar qabul qilinadi."), code="invalid_type")
    if allowed is None:
        raise invalid
    upload.seek(0)
    head = upload.read(4096)
    upload.seek(0)
    sniffed = magic.from_buffer(head, mime=True)
    if sniffed not in allowed:
        raise invalid
    if extension == "docx":
        try:
            with zipfile.ZipFile(upload) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise invalid
        except zipfile.BadZipFile as exc:
            raise invalid from exc
        finally:
            upload.seek(0)
        sniffed = DOCX_MIME
    return CheckedAttachment(upload=upload, extension=extension, mime_type=sniffed)


def hash_ip(ip: str) -> str:
    """Keyed hash so repeated abuse is traceable without storing the raw address."""
    if not ip:
        return ""
    return hmac.new(settings.SECRET_KEY.encode(), f"appeal|{ip}".encode(), hashlib.sha256).hexdigest()


def rate_limited(request: HttpRequest, *, increment: bool) -> bool:
    """Shared 5/hour/IP budget of the form and the API; only accepted submissions consume it."""
    usage = get_usage(
        request,
        group=RATE_LIMIT_GROUP,
        key="ip",
        rate=RATE_LIMIT,
        method=["POST"],
        increment=increment,
    )
    if not usage:
        return False
    if increment:
        return bool(usage["should_limit"])
    return bool(usage["count"] >= usage["limit"])  # peek: the next accepted submission would exceed it


def turnstile_enabled() -> bool:
    return bool(settings.TURNSTILE_SITE_KEY and settings.TURNSTILE_SECRET_KEY)


def verify_turnstile(token: str, ip: str) -> bool:
    """True when Turnstile is disabled (no keys) or Cloudflare confirms the token; fails closed."""
    if not turnstile_enabled():
        return True
    if not token:
        return False
    try:
        response = httpx.post(
            TURNSTILE_VERIFY_URL,
            data={"secret": settings.TURNSTILE_SECRET_KEY, "response": token, "remoteip": ip},
            timeout=10,
        )
        return bool(response.json().get("success"))
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("turnstile_verify_failed", error=str(exc))
        return False


def generate_tracking_code(now: Any = None) -> str:
    """`EDC-YYYY-NNNNNN` with random digits (not sequential, so codes cannot be enumerated in order)."""
    year = (now or timezone.localtime()).year
    return f"{TRACKING_PREFIX}-{year}-{secrets.randbelow(1_000_000):06d}"


def create_appeal(data: AppealInput) -> Appeal:
    """Persist the appeal (+ attachment) and queue the confirmation/moderator alerts after commit."""
    from apps.appeals.tasks import notify_new

    checked = validate_attachment(data.attachment) if data.attachment is not None else None
    with transaction.atomic():
        appeal = _insert_with_unique_code(data)
        if checked is not None:
            AppealAttachment.objects.create(
                appeal=appeal,
                file=checked.upload,
                original_name=(checked.upload.name or "file")[:255],
                size_bytes=checked.upload.size or 0,
                mime_type=checked.mime_type,
            )
        transaction.on_commit(lambda: notify_new.delay(appeal.pk))
    log.info("appeal_created", appeal_id=appeal.pk, tracking_code=appeal.tracking_code)
    return appeal


def _insert_with_unique_code(data: AppealInput) -> Appeal:
    for _attempt in range(5):
        try:
            with transaction.atomic():  # savepoint: a code collision does not abort the outer transaction
                return Appeal.objects.create(
                    tracking_code=generate_tracking_code(),
                    institution=data.institution,
                    topic=data.topic,
                    full_name=data.full_name.strip(),
                    phone=data.phone,
                    email=data.email.strip(),
                    message=data.message.strip(),
                    consent=data.consent,
                    ip_hash=hash_ip(data.ip),
                    user_agent=data.user_agent[:300],
                    locale=data.locale[:10] or "uz",
                )
        except IntegrityError:
            continue
    raise RuntimeError("could not allocate a unique tracking code")  # pragma: no cover
