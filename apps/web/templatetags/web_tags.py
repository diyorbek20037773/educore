"""Template helpers for the public site: icons, Uzbek dates, time-ago, sparklines, language URLs, JSON-LD."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from django import template
from django.templatetags.static import static
from django.urls import translate_url
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe
from django.utils.translation import get_language, gettext

register = template.Library()

MONTHS_UZ = [
    "yanvar",
    "fevral",
    "mart",
    "aprel",
    "may",
    "iyun",
    "iyul",
    "avgust",
    "sentabr",
    "oktabr",
    "noyabr",
    "dekabr",
]
MONTHS_RU = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]
MONTHS_EN = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
WEEKDAYS_UZ = ["dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba"]
WEEKDAYS_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
WEEKDAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _lang() -> str:
    return (get_language() or "uz").lower()


DECORATIVE = mark_safe('aria-hidden="true" focusable="false"')  # noqa: S308 - constant
ICON_SVG = (
    '<svg class="{}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" {}><use href="{}#{}"></use></svg>'
)

# Lucide renamed these; icon names stored in the database (categories, professions) may use the old ones.
ICON_ALIASES = {
    "home": "house",
    "fingerprint": "fingerprint-pattern",
    "building-2": "building",
    "bar-chart-3": "chart-column",
    "line-chart": "chart-line",
    "filter": "funnel",
}


@register.simple_tag
def icon(name: str, css: str = "size-5", label: str = "") -> SafeString:
    """Lucide icon from the subset sprite (`make icons`); decorative unless `label` is given."""
    sprite = static("icons/sprite.svg")
    name = ICON_ALIASES.get(name, name)
    if label:
        return format_html(ICON_SVG, css, format_html('role="img" aria-label="{}"', label), sprite, name)
    return format_html(ICON_SVG, css, DECORATIVE, sprite, name)


def _localize(value: str) -> str:
    from apps.core.translit import to_cyrillic

    return to_cyrillic(value) if _lang() == "uz-cyrl" else value


@register.filter
def uz_date(value: date | datetime | None, with_year: bool = True) -> str:
    """ "25-sentabr, 2026-yil" (uz), "25 сентября 2026" (ru), "25 September 2026" (en)."""
    if not value:
        return ""
    if isinstance(value, datetime):
        value = timezone.localtime(value) if timezone.is_aware(value) else value
    lang = _lang()
    if lang == "ru":
        return f"{value.day} {MONTHS_RU[value.month - 1]}" + (f" {value.year}" if with_year else "")
    if lang == "en":
        return f"{value.day} {MONTHS_EN[value.month - 1]}" + (f" {value.year}" if with_year else "")
    text = f"{value.day}-{MONTHS_UZ[value.month - 1]}" + (f", {value.year}-yil" if with_year else "")
    return _localize(text)


@register.filter
def uz_datetime(value: datetime | None) -> str:
    if not value:
        return ""
    local = timezone.localtime(value)
    return f"{uz_date(local)}, {local:%H:%M}"


@register.simple_tag
def today_label() -> str:
    """Top-bar date: "Payshanba, 25-sentabr, 2026-yil"."""
    now = timezone.localtime()
    lang = _lang()
    names = WEEKDAYS_RU if lang == "ru" else WEEKDAYS_EN if lang == "en" else WEEKDAYS_UZ
    day = names[now.weekday()]
    return f"{_localize(day.capitalize()) if lang.startswith('uz') else day.capitalize()}, {uz_date(now)}"


@register.filter
def time_ago(value: datetime | None) -> str:
    """ "5 daqiqa oldin" — relative time in the active language."""
    if not value:
        return ""
    seconds = max(0, int((timezone.now() - value).total_seconds()))
    if seconds < 60:
        return gettext("hozirgina")
    minutes, hours, days = seconds // 60, seconds // 3600, seconds // 86400
    if minutes < 60:
        return gettext("%(n)d daqiqa oldin") % {"n": minutes}
    if hours < 24:
        return gettext("%(n)d soat oldin") % {"n": hours}
    if days < 7:
        return gettext("%(n)d kun oldin") % {"n": days}
    return uz_date(value)


@register.simple_tag
def sparkline(
    values: Sequence[float] | None, color: str = "currentColor", width: int = 120, height: int = 32
) -> SafeString:
    """Inline SVG sparkline (SPEC §7.4 — no ECharts for tiles)."""
    points = [float(v) for v in (values or [])]
    if len(points) < 2:
        return mark_safe("")  # noqa: S308 - static empty string
    low, high = min(points), max(points)
    span = (high - low) or 1.0
    step = width / (len(points) - 1)
    coords = " ".join(
        f"{i * step:.1f},{height - 2 - (v - low) / span * (height - 4):.1f}" for i, v in enumerate(points)
    )
    return format_html(
        '<svg class="sparkline" viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true" '
        'focusable="false">'
        '<polyline fill="none" stroke="{c}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" '
        'points="{p}"/></svg>',
        w=width,
        h=height,
        c=color,
        p=coords,
    )


@register.simple_tag(takes_context=True)
def language_url(context: dict[str, Any], lang_code: str) -> str:
    """The current page in another language (keeps the path; falls back to the home page)."""
    request = context.get("request")
    path = request.get_full_path() if request else "/"
    return translate_url(path, lang_code) or "/"


@register.filter
def jsonld(value: Any) -> SafeString:
    """Safe JSON for `<script type="application/ld+json">` blocks."""
    text = json.dumps(value, ensure_ascii=False, default=str)
    text = text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return mark_safe(text)  # noqa: S308 - escaped above


@register.filter
def translated(obj: Any, field: str) -> bool:
    """False when the active language has no own value for `field` (the uz fallback is shown)."""
    lang = _lang()
    if lang == "uz":
        return True
    suffix = lang.replace("-", "_")
    return bool(getattr(obj, f"{field}_{suffix}", None))


@register.filter
def intcomma_uz(value: Any) -> str:
    """ "12 500" — thin-space thousands separator (SPEC style)."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "—" if value in (None, "") else str(value)
    return f"{number:,}".replace(",", " ")


@register.filter
def get_item(mapping: dict[Any, Any], key: Any) -> Any:
    return (mapping or {}).get(key)


@register.filter
def month_short(value: date | datetime | None) -> str:
    """Three-letter month for date blocks ("sen", "сен", "Sep")."""
    if not value:
        return ""
    lang = _lang()
    if lang == "ru":
        return MONTHS_RU[value.month - 1][:3]
    if lang == "en":
        return MONTHS_EN[value.month - 1][:3]
    return _localize(MONTHS_UZ[value.month - 1][:3])


@register.filter
def make_list_if_str(value: Any) -> list[Any]:
    """`"A,B"` → `["A", "B"]`; lists/tuples pass through (template defaults)."""
    if isinstance(value, str):
        return [v for v in value.split(",") if v]
    return list(value or [])


@register.filter
def is_recent(value: datetime | None, seconds: int = 90) -> bool:
    """True for items published within the last live-panel refresh window (highlight)."""
    return bool(value) and (timezone.now() - value).total_seconds() <= seconds
