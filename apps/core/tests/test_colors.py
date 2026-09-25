"""Color validators and the ADR-007 institution palette."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.core.colors import contrast_ratio, validate_hex_color, validate_text_color_on_white

# SPEC §7.4 — (chart color, text color) in `Institution.order`.
PALETTE = [
    ("#E4552F", "#B93A1E"),
    ("#2B6FD6", "#1F55B0"),
    ("#1FA463", "#177A49"),
    ("#9C4DC4", "#7A36A0"),
    ("#0E97A5", "#0B7381"),
]


def test_contrast_extremes() -> None:
    assert contrast_ratio("#000000") == pytest.approx(21.0)
    assert contrast_ratio("#FFFFFF") == pytest.approx(1.0)


@pytest.mark.parametrize(("color", "text"), PALETTE)
def test_palette_text_colors_meet_aa(color: str, text: str) -> None:
    validate_hex_color(color)
    validate_text_color_on_white(text)
    assert contrast_ratio(text) >= 4.5


@pytest.mark.parametrize(("color", "_text"), PALETTE)
def test_palette_chart_colors_reach_3_to_1_on_light_and_dark(color: str, _text: str) -> None:
    assert contrast_ratio(color, "#FCFCFB") >= 3.0
    assert contrast_ratio(color, "#0B1220") >= 3.0


@pytest.mark.parametrize("value", ["", "red", "#12345", "#GGGGGG", "123456"])
def test_invalid_hex_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        validate_hex_color(value)


def test_low_contrast_text_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_text_color_on_white("#E4552F")
