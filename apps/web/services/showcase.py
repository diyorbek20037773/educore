"""Institution showcase for the "rankings skin" layout of `/muassasalar/` (ADR-031).

Every number shown in the banner and the side rails is computed from data the platform already holds:
activity ranks among the five institutions (published articles), counts of programs and upcoming events,
and `InstitutionMetric` values that an editor has verified. Nothing is invented; an institution without
data simply shows fewer badges.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db.models import Count, Q
from django.utils.translation import gettext as _

from apps.content.models import ArticleStatus
from apps.institutions.models import Institution, InstitutionMetric, MetricKey

MAX_BADGES = 4
# Verified metrics worth a badge, in display priority order.
BADGE_METRICS = (MetricKey.STUDENTS, MetricKey.CADETS, MetricKey.FACULTY, MetricKey.PARTNERS)


@dataclass
class Badge:
    """One rail badge: a big red number, short lines under it (the last one red), a spoken label."""

    number: str
    lines: list[str]
    aria: str


@dataclass
class Showcase:
    """Banner + rail content for one institution."""

    institution: Institution
    badges: list[Badge] = field(default_factory=list)
    banner_highlight: str = ""
    banner_sub: str = ""
    stat_top: str = ""
    stat_value: str = ""


def activity_totals() -> dict[int, dict[str, Any]]:
    """Published article totals and verified metrics per institution (cacheable, language-neutral)."""
    totals = {
        row["pk"]: {"articles": row["articles_total"], "metrics": {}}
        for row in Institution.objects.filter(is_active=True)
        .annotate(
            articles_total=Count(
                "primary_articles", filter=Q(primary_articles__status=ArticleStatus.PUBLISHED)
            )
        )
        .values("pk", "articles_total")
    }
    metrics = InstitutionMetric.objects.filter(
        institution__is_active=True, needs_verification=False, value__isnull=False, key__in=BADGE_METRICS
    ).order_by("year")
    for metric in metrics:  # ascending year: the latest year wins
        totals.setdefault(metric.institution_id, {"articles": 0, "metrics": {}})["metrics"][metric.key] = (
            metric.value
        )
    return totals


def dense_ranks(values: dict[int, int]) -> dict[int, int]:
    """Dense rank (1 = highest) of positive values; zero or missing values get no rank."""
    distinct = sorted({v for v in values.values() if v > 0}, reverse=True)
    position = {value: index + 1 for index, value in enumerate(distinct)}
    return {pk: position[v] for pk, v in values.items() if v > 0}


def _lines(text: str) -> list[str]:
    """Badge lines come as one translatable phrase split on "|" so translators can reorder words."""
    return [part.strip() for part in text.split("|") if part.strip()]


def _fmt(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def build_showcase(cards: list[dict[str, Any]], totals: dict[int, dict[str, Any]]) -> list[Showcase]:
    """Combine the cached institution cards and totals into per-institution showcase items.

    Runs per request (cheap, no queries) so every label is translated into the active language.
    """
    institutions: list[Institution] = [card["institution"] for card in cards]
    news_rank = dense_ranks({i.pk: getattr(i, "news_30", 0) or 0 for i in institutions})
    article_rank = dense_ranks({i.pk: totals.get(i.pk, {}).get("articles", 0) for i in institutions})
    labels = dict(MetricKey.choices)
    items = []
    for inst in institutions:
        data = totals.get(inst.pk, {"articles": 0, "metrics": {}})
        badges: list[Badge] = []
        if inst.pk in news_rank:
            rank = news_rank[inst.pk]
            badges.append(
                Badge(
                    f"#{rank}",
                    _lines(_("30 kunda|yangiliklar|soni boʻyicha")),
                    _("30 kunlik yangiliklar soni boʻyicha %(rank)s-oʻrin") % {"rank": rank},
                )
            )
        if inst.pk in article_rank:
            rank = article_rank[inst.pk]
            badges.append(
                Badge(
                    f"#{rank}",
                    _lines(_("jami|rasmiy|maqolalar")),
                    _("Jami rasmiy maqolalar soni boʻyicha %(rank)s-oʻrin") % {"rank": rank},
                )
            )
        for key in BADGE_METRICS:
            value = data["metrics"].get(key)
            if value:
                label = str(labels[key])
                badges.append(Badge(_fmt(value), [label], f"{label}: {value}"))
        programs = getattr(inst, "programs_n", 0) or 0
        if programs:
            badges.append(
                Badge(
                    str(programs),
                    _lines(_("taʼlim|yoʻnalishi")),
                    _("%(n)s ta taʼlim yoʻnalishi") % {"n": programs},
                )
            )
        events = getattr(inst, "events_n", 0) or 0
        if events:
            badges.append(
                Badge(str(events), _lines(_("yaqin|tadbir")), _("%(n)s ta yaqin tadbir") % {"n": events})
            )
        if inst.founded_year:
            badges.append(
                Badge(
                    str(inst.founded_year),
                    _lines(_("yilda|tashkil|topgan")),
                    _("%(year)s-yilda tashkil topgan") % {"year": inst.founded_year},
                )
            )
        item = Showcase(institution=inst, badges=badges[:MAX_BADGES])
        if inst.pk in news_rank:
            item.banner_highlight = f"#{news_rank[inst.pk]}"
            item.banner_sub = _("(30 kunlik faollik boʻyicha)")
        if data["articles"]:
            item.stat_top = _("Platformadagi rasmiy maqolalar")
            item.stat_value = _fmt(data["articles"])
        elif inst.telegram_username:
            item.stat_top = _("Rasmiy Telegram kanali")
            item.stat_value = f"@{inst.telegram_username}"
        items.append(item)
    return items


def split_rails(items: list[Showcase]) -> tuple[list[Showcase], list[Showcase]]:
    """Left rail starts with the first institution, right rail with the second, both cycle through all.

    Each rail rotates through every institution, offset by one so the two rails never show the same one.
    """
    if len(items) < 2:
        return items, items
    return items, items[1:] + items[:1]
