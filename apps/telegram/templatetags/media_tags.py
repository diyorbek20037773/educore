"""`{% media_url media "800" %}` and `{% media_srcset media %}` with graceful fallbacks (T2.4)."""

from __future__ import annotations

from django import template

from apps.telegram.models import TelegramMedia
from apps.telegram.storage import DERIVATIVE_SIZES
from apps.telegram.storage import media_url as storage_url

register = template.Library()


@register.simple_tag
def media_url(media: TelegramMedia | None, size: str = "800") -> str:
    """Derivative URL for `size`, else the closest available derivative, else the original photo, else ""."""
    if media is None:
        return ""
    derivatives = media.derivatives or {}
    if derivatives.get(size):
        return storage_url(derivatives[size])
    for candidate in (*DERIVATIVE_SIZES, "poster"):
        if derivatives.get(candidate):
            return storage_url(derivatives[candidate])
    if media.kind == "photo" and media.original:
        return storage_url(media.original.name)
    return ""


@register.simple_tag
def media_srcset(media: TelegramMedia | None) -> str:
    """`srcset` value from the WebP derivatives (`url 400w, url 800w, url 1600w`)."""
    if media is None:
        return ""
    derivatives = media.derivatives or {}
    parts = [f"{storage_url(derivatives[s])} {s}w" for s in reversed(DERIVATIVE_SIZES) if derivatives.get(s)]
    return ", ".join(parts)


@register.simple_tag
def media_file_url(media: TelegramMedia | None) -> str:
    """URL of the stored original file (videos are played from it), or ""."""
    if media is None or not media.original:
        return ""
    return storage_url(media.original.name)
