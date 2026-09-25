"""Media storage abstraction (SPEC FR-TG-4, T2.4): path scheme and URLs for `local` and `s3` backends."""

from __future__ import annotations

from datetime import datetime

from django.core.files.storage import Storage, storages

DERIVATIVE_SIZES: tuple[str, ...] = ("1600", "800", "400")


def media_storage() -> Storage:
    """The configured default storage (FileSystemStorage for `local`, S3Storage for `s3`)."""
    return storages["default"]


def original_path(username: str, published_at: datetime, message_id: int, order: int, ext: str) -> str:
    """`telegram/{username}/{yyyy}/{mm}/{message_id}/{n}.{ext}`."""
    ext = (ext or "bin").lower().lstrip(".")
    return f"telegram/{username}/{published_at:%Y}/{published_at:%m}/{message_id}/{order}.{ext}"


def derivative_path(original: str, size: str) -> str:
    """Derivative next to its original: `…/{n}.jpg` → `…/{n}_800.webp`, poster → `…/{n}_poster.webp`."""
    stem = original.rsplit(".", 1)[0]
    return f"{stem}_{size}.webp"


def media_url(key: str | None) -> str:
    """Public URL for a storage key (empty string when missing)."""
    if not key:
        return ""
    return media_storage().url(key)
