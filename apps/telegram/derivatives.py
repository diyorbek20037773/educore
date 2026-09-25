"""Media derivatives (FR-TG-4): WebP 1600/800/400 for photos, poster frame (+ sizes) for videos."""

from __future__ import annotations

import io
import subprocess
import tempfile
from pathlib import Path

import structlog
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from apps.telegram.models import MediaStatus, TelegramMedia
from apps.telegram.storage import DERIVATIVE_SIZES, derivative_path, media_storage

log = structlog.get_logger(__name__)
WEBP_QUALITY = 82
IMAGE_KINDS = frozenset({"photo"})
VIDEO_KINDS = frozenset({"video", "animation"})


def _webp_bytes(image: Image.Image, width: int) -> bytes:
    img = image.copy()
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, "WEBP", quality=WEBP_QUALITY, method=6)
    return buffer.getvalue()


def _save(key: str, data: bytes) -> str:
    storage = media_storage()
    if storage.exists(key):
        storage.delete(key)
    return storage.save(key, ContentFile(data))


def image_derivatives(image: Image.Image, original_key: str) -> dict[str, str]:
    """Save the WebP sizes (never upscaled) and return {size: storage key}."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    return {
        size: _save(derivative_path(original_key, size), _webp_bytes(image, int(size)))
        for size in DERIVATIVE_SIZES
    }


def video_poster(local_video: str) -> Image.Image:
    """First meaningful frame (at 1 s, or 0 s for very short clips) via ffmpeg."""
    with tempfile.TemporaryDirectory(prefix="educore-poster-") as tmp:
        out = Path(tmp) / "poster.png"
        for position in ("00:00:01", "00:00:00"):
            cmd = [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-ss",
                position,
                "-i",
                local_video,
                "-frames:v",
                "1",
                str(out),
            ]
            subprocess.run(cmd, check=False, timeout=60)  # noqa: S603 - fixed argv, no shell
            if out.exists() and out.stat().st_size:
                with Image.open(out) as frame:
                    return frame.copy()
    raise RuntimeError("ffmpeg could not extract a poster frame")


def process_media(media_id: int) -> str:
    """Generate derivatives for one downloaded media row; returns the final status."""
    media = TelegramMedia.objects.filter(pk=media_id).first()
    if media is None or not media.original:
        return "missing"
    if media.status == MediaStatus.READY and media.derivatives:
        return MediaStatus.READY
    storage = media_storage()
    try:
        if media.kind in IMAGE_KINDS:
            with storage.open(media.original.name, "rb") as fh, Image.open(fh) as image:
                derivatives = image_derivatives(image, media.original.name)
                width, height = image.size
        elif media.kind in VIDEO_KINDS:
            suffix = Path(media.original.name).suffix or ".mp4"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                with storage.open(media.original.name, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                        tmp.write(chunk)
                local = tmp.name
            try:
                poster = video_poster(local)
            finally:
                Path(local).unlink(missing_ok=True)
            derivatives = image_derivatives(poster, media.original.name)
            derivatives["poster"] = derivatives[DERIVATIVE_SIZES[0]]
            width, height = media.width or poster.width, media.height or poster.height
        else:  # documents/audio: nothing to render
            TelegramMedia.objects.filter(pk=media_id).update(status=MediaStatus.READY)
            return MediaStatus.READY
    except Exception as exc:
        log.warning("media_derivatives_failed", media_id=media_id, error=str(exc))
        TelegramMedia.objects.filter(pk=media_id).update(
            status=MediaStatus.FAILED, error=f"derivatives: {exc}"[:500]
        )
        return MediaStatus.FAILED
    TelegramMedia.objects.filter(pk=media_id).update(
        derivatives=derivatives, status=MediaStatus.READY, width=width, height=height, error=""
    )
    return MediaStatus.READY
