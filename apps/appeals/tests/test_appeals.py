"""Appeals: submission, rate limit, honeypot, attachments, tracking, workflow, anonymization (T6.4)."""

from __future__ import annotations

import io
import zipfile
from datetime import date, timedelta
from typing import Any
from unittest import mock

import pytest
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.appeals.models import Appeal, AppealAttachment, AppealMessage, AppealStatus
from apps.appeals.services import submission, workflow
from apps.appeals.tests.factories import AppealFactory, AppealMessageFactory

pytestmark = pytest.mark.django_db


def _png() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
    return buffer.getvalue()


PNG = _png()
PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
VALID = {
    "topic": "qabul",
    "full_name": "Ali Valiyev",
    "phone": "+998 90 123 45 67",
    "email": "ali@example.uz",
    "message": "Qabul hujjatlari boʻyicha savolim bor, iltimos javob bering.",
    "consent": "on",
}


@pytest.fixture(autouse=True)
def _clean_cache(settings: Any) -> Any:
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.TURNSTILE_SITE_KEY = ""
    settings.TURNSTILE_SECRET_KEY = ""
    cache.clear()
    yield
    cache.clear()


def _docx() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")
    return buffer.getvalue()


def test_submit_happy_path_with_attachment(client: Client, django_capture_on_commit_callbacks: Any) -> None:
    upload = SimpleUploadedFile("ariza.pdf", PDF, content_type="application/pdf")
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(reverse("web:appeal_form"), {**VALID, "attachment": upload})
    appeal = Appeal.objects.get()
    assert response.status_code == 302
    assert response["Location"] == reverse("web:appeal_success", kwargs={"code": appeal.tracking_code})
    assert appeal.tracking_code.startswith(f"EDC-{timezone.localdate().year}-")
    assert appeal.phone == "+998901234567" and appeal.ip_hash and appeal.status == AppealStatus.NEW
    attachment = AppealAttachment.objects.get()
    assert attachment.mime_type == "application/pdf" and attachment.original_name == "ariza.pdf"
    assert "ariza" not in attachment.file.name  # opaque name in private storage
    # confirmation e-mail with the tracking code
    assert len(mail.outbox) == 1 and appeal.tracking_code in mail.outbox[0].body
    assert mail.outbox[0].to == ["ali@example.uz"]
    success = client.get(response["Location"]).content.decode()
    assert appeal.tracking_code in success


def test_moderators_alerted_without_pii(settings: Any, django_capture_on_commit_callbacks: Any) -> None:
    from apps.ops.models import AlertEvent

    settings.APPEALS_NOTIFY_EMAILS = ["mod@example.uz"]
    with django_capture_on_commit_callbacks(execute=True):
        appeal = submission.create_appeal(
            submission.AppealInput(
                topic="taklif", full_name="Ali", phone="+998901234567", message="x" * 30, consent=True
            )
        )
    alert = AlertEvent.objects.get(kind="appeal_new")
    assert appeal.tracking_code in alert.message and "Ali" not in alert.message
    assert [m.to for m in mail.outbox] == [["mod@example.uz"]]  # no applicant e-mail given


def test_rate_limit_five_per_hour(client: Client) -> None:
    url = reverse("web:appeal_form")
    for _ in range(5):
        assert client.post(url, VALID).status_code == 302
    response = client.post(url, VALID)
    assert response.status_code == 429 and response["Retry-After"] == "3600"
    assert Appeal.objects.count() == 5


def test_invalid_submissions_do_not_consume_the_limit(client: Client) -> None:
    url = reverse("web:appeal_form")
    for _ in range(6):
        assert client.post(url, {**VALID, "phone": "123"}).status_code == 200
    assert client.post(url, VALID).status_code == 302


def test_honeypot_stores_nothing(client: Client) -> None:
    response = client.post(reverse("web:appeal_form"), {**VALID, "website": "http://spam"})
    assert response.status_code == 302 and Appeal.objects.count() == 0


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("virus.exe", b"MZ\x90\x00"),
        ("fake.pdf", b"MZ\x90\x00 not a pdf"),
        ("photo.png", PDF),
        ("doc.docx", b"PK\x03\x04 broken"),
    ],
)
def test_invalid_file_rejected(client: Client, name: str, content: bytes) -> None:
    upload = SimpleUploadedFile(name, content, content_type="application/pdf")
    response = client.post(reverse("web:appeal_form"), {**VALID, "attachment": upload})
    assert response.status_code == 200 and 'id="attachment-error"' in response.content.decode()
    assert Appeal.objects.count() == 0


def test_oversized_file_rejected() -> None:
    upload = SimpleUploadedFile("big.png", PNG + b"\x00" * (5 * 1024 * 1024), content_type="image/png")
    with pytest.raises(Exception, match="5 MB"):
        submission.validate_attachment(upload)


def test_accepted_file_types() -> None:
    assert submission.validate_attachment(SimpleUploadedFile("a.png", PNG)).mime_type == "image/png"
    assert (
        submission.validate_attachment(SimpleUploadedFile("a.docx", _docx())).mime_type
        == submission.DOCX_MIME
    )


def test_turnstile_required_when_enabled(client: Client, settings: Any) -> None:
    settings.TURNSTILE_SITE_KEY = "site"
    settings.TURNSTILE_SECRET_KEY = "secret"
    url = reverse("web:appeal_form")
    assert "challenges.cloudflare.com/turnstile" in client.get(url).content.decode()
    with mock.patch("apps.appeals.services.submission.httpx.post") as post:
        post.return_value.json.return_value = {"success": False}
        assert client.post(url, {**VALID, "cf-turnstile-response": "bad"}).status_code == 200
        post.return_value.json.return_value = {"success": True}
        assert client.post(url, {**VALID, "cf-turnstile-response": "ok"}).status_code == 302
    assert Appeal.objects.count() == 1


def test_tracking_page_shows_timeline_and_public_replies(client: Client, admin_user: Any) -> None:
    appeal = AppealFactory()
    AppealMessageFactory(appeal=appeal, author=admin_user, body="Ochiq javob", is_public=True)
    AppealMessageFactory(appeal=appeal, author=admin_user, body="Ichki izoh", is_public=False)
    workflow.change_status([appeal], AppealStatus.ANSWERED)
    body = client.get(reverse("web:appeal_track"), {"code": appeal.tracking_code.lower()}).content.decode()
    assert "Ochiq javob" in body and "Ichki izoh" not in body
    assert 'aria-current="step"' in body and "Javob berildi" in body


def test_staff_reply_answers_and_emails(admin_user: Any, django_capture_on_commit_callbacks: Any) -> None:
    appeal = AppealFactory(email="ali@example.uz")
    with django_capture_on_commit_callbacks(execute=True):
        message = workflow.add_reply(appeal, admin_user, "Hujjatlar 1-iyulgacha qabul qilinadi.")
    appeal.refresh_from_db()
    message.refresh_from_db()
    assert appeal.status == AppealStatus.ANSWERED and appeal.answered_at is not None
    assert message.notified_at is not None
    assert len(mail.outbox) == 1 and "1-iyulgacha" in mail.outbox[0].body


def test_internal_note_is_not_emailed(admin_user: Any, django_capture_on_commit_callbacks: Any) -> None:
    appeal = AppealFactory(email="ali@example.uz")
    with django_capture_on_commit_callbacks(execute=True):
        workflow.add_reply(appeal, admin_user, "ichki", is_public=False)
    appeal.refresh_from_db()
    assert appeal.status == AppealStatus.NEW and mail.outbox == []


def test_sla_overdue_counts_working_days() -> None:
    assert workflow.working_days_ago(15, date(2026, 9, 25)) == date(2026, 9, 4)  # Friday → 3 weeks back
    old = AppealFactory()
    Appeal.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=30))
    AppealFactory()
    closed = AppealFactory(status=AppealStatus.CLOSED)
    Appeal.objects.filter(pk=closed.pk).update(created_at=timezone.now() - timedelta(days=30))
    assert list(workflow.overdue(Appeal.objects.all())) == [old]


def test_csv_export_neutralizes_formulas() -> None:
    AppealFactory(full_name="Ali", message="=HYPERLINK(1)")
    csv_text = workflow.export_csv(Appeal.objects.all())
    assert csv_text.startswith("﻿tracking_code") and "'=HYPERLINK(1)" in csv_text


def test_anonymize_appeals_command(admin_user: Any) -> None:
    old = AppealFactory(full_name="Ali Valiyev", email="ali@example.uz", status=AppealStatus.CLOSED)
    AppealAttachment.objects.create(
        appeal=old,
        file=SimpleUploadedFile("a.png", PNG),
        original_name="a.png",
        size_bytes=10,
        mime_type="image/png",
    )
    AppealMessageFactory(appeal=old, author=None, body="shaxsiy matn")
    Appeal.objects.filter(pk=old.pk).update(closed_at=timezone.now() - timedelta(days=800))
    recent = AppealFactory(full_name="Vali", status=AppealStatus.CLOSED, closed_at=timezone.now())
    open_old = AppealFactory(full_name="Soli")
    call_command("anonymize_appeals")
    old.refresh_from_db()
    assert old.full_name == workflow.ANONYMIZED_NAME and old.email == "" and old.phone == ""
    assert old.anonymized_at is not None and not old.attachments.exists()
    assert AppealMessage.objects.get(appeal=old).body == workflow.ANONYMIZED_TEXT
    assert not old.history.filter(full_name="Ali Valiyev").exists()
    recent.refresh_from_db()
    open_old.refresh_from_db()
    assert recent.full_name == "Vali" and open_old.full_name == "Soli"
    call_command("anonymize_appeals")  # idempotent
    assert workflow.anonymization_candidates().count() == 0


def test_attachment_download_is_staff_only(client: Client, verified_admin_client: Client) -> None:
    appeal = AppealFactory()
    attachment = AppealAttachment.objects.create(
        appeal=appeal,
        file=SimpleUploadedFile("a.png", PNG),
        original_name="a.png",
        size_bytes=72,
        mime_type="image/png",
    )
    url = reverse("admin:appeals_appeal_attachment", args=[appeal.pk, attachment.pk])
    assert client.get(url).status_code == 302  # anonymous → login
    response = verified_admin_client.get(url)
    assert response.status_code == 200 and b"".join(response.streaming_content) == PNG
    assert "no-store" in response["Cache-Control"]
