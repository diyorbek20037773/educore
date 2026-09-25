"""Color helpers: hex validation and WCAG contrast ratio (SPEC §2.3 `color_text` ≥ 4.5:1 on white)."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
WHITE = "#FFFFFF"


def validate_hex_color(value: str) -> None:
    """Reject anything that is not a ``#RRGGBB`` color."""
    if not HEX_RE.match(value or ""):
        raise ValidationError(_("Enter a color as #RRGGBB."), code="invalid_hex")


def _channel(value: int) -> float:
    c = value / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """WCAG 2.1 relative luminance of a ``#RRGGBB`` color."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(foreground: str, background: str = WHITE) -> float:
    """WCAG contrast ratio between two colors (1.0 … 21.0)."""
    lighter, darker = sorted((relative_luminance(foreground), relative_luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def validate_text_color_on_white(value: str) -> None:
    """Text colors must reach 4.5:1 against white (WCAG AA body text)."""
    validate_hex_color(value)
    if contrast_ratio(value) < 4.5:
        raise ValidationError(
            _("Contrast on white is %(ratio).2f:1; at least 4.5:1 is required."),
            code="low_contrast",
            params={"ratio": contrast_ratio(value)},
        )
