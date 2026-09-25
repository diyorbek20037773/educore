"""Chart payloads for `/analitika/data/<chart>/` (SPEC §6.9, §7.4).

Every builder returns the `charts.js` contract: `kind`, `categories`, `series` (institution series carry the
fixed palette colour from `Institution.color`, ADR-007) and a `table` used for the table view and CSV.
Time series read the daily rollups (`InstitutionDailyStat`); today's row is refreshed hourly (ADR-026).
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.analytics.models import InstitutionDailyStat
from apps.content.models import ArticleStatus, Category, Tag
from apps.institutions.models import Institution, InstitutionMetric, MetricKey

MAX_DAYS = 730
WEEKDAYS = ("Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya")


class ChartParams:
    """Parsed, clamped query parameters shared by every chart."""

    def __init__(self, query: Any) -> None:
        period = query.get("period", "")
        if period == "12m":
            self.days = 365
        else:
            try:
                self.days = int(query.get("days", "30"))
            except ValueError:
                self.days = 30
        self.days = max(7, min(self.days, MAX_DAYS))
        self.monthly = period == "12m" or self.days > 180
        self.institution_slugs = [s for s in query.get("inst", "").split(",") if s][:5]
        self.metric = query.get("metric", "")

    @property
    def since(self) -> Any:
        return timezone.now() - timedelta(days=self.days)

    def institutions(self) -> list[Institution]:
        qs = Institution.objects.filter(is_active=True).order_by("order")
        if self.institution_slugs:
            qs = qs.filter(slug__in=self.institution_slugs)
        return list(qs)


def _periods(params: ChartParams) -> list[date]:
    today = timezone.localdate()
    if params.monthly:
        first = today.replace(day=1)
        months = []
        for _i in range(12 if params.days <= 365 else 24):
            months.append(first)
            first = (first - timedelta(days=1)).replace(day=1)
        return list(reversed(months))
    if params.days > 90:
        monday = today - timedelta(days=today.weekday())
        return [monday - timedelta(weeks=n) for n in reversed(range(params.days // 7 + 1))]
    return [today - timedelta(days=n) for n in reversed(range(params.days))]


def _period_label(day: date, params: ChartParams) -> str:
    return day.strftime("%Y-%m") if params.monthly else day.strftime("%d.%m")


def _stats(params: ChartParams, institutions: list[Institution]) -> list[InstitutionDailyStat]:
    since = timezone.localdate() - timedelta(days=params.days - 1)
    return list(
        InstitutionDailyStat.objects.filter(date__gte=since, institution__in=institutions).order_by("date")
    )


def _bucket(day: date, params: ChartParams) -> date:
    if params.monthly:
        return day.replace(day=1)
    if params.days > 90:
        return day - timedelta(days=day.weekday())
    return day


def activity(params: ChartParams) -> dict[str, Any]:
    """Published articles per institution over time (daily rollups) — one line each, fixed colours."""
    institutions = params.institutions()
    periods = _periods(params)
    counts: dict[int, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    for stat in _stats(params, institutions):
        counts[stat.institution_id][_bucket(stat.date, params)] += stat.articles
    categories = [_period_label(p, params) for p in periods]
    series = [
        {"name": i.abbreviation, "color": i.color, "data": [counts[i.pk].get(p, 0) for p in periods]}
        for i in institutions
    ]
    return {
        "kind": "line",
        "categories": categories,
        "series": series,
        "table": {
            "columns": [_("Davr"), *[s["name"] for s in series]],
            "rows": [[c, *[s["data"][n] for s in series]] for n, c in enumerate(categories)],
        },
    }


def categories(params: ChartParams) -> dict[str, Any]:
    """Published articles by category — horizontal bars in a single hue."""
    totals: dict[str, int] = defaultdict(int)
    for stat in _stats(params, params.institutions()):
        for slug, n in (stat.by_category or {}).items():
            totals[slug] += n
    names = dict(Category.objects.values_list("slug", "name"))
    data = sorted(((names.get(slug, _("Boshqa")), n) for slug, n in totals.items() if n), key=lambda d: -d[1])
    return {
        "kind": "hbar",
        "categories": [d[0] for d in data],
        "series": [{"name": _("Maqolalar"), "data": [d[1] for d in data]}],
        "table": {"columns": [_("Kategoriya"), _("Maqolalar")], "rows": [list(d) for d in data]},
    }


def heatmap(params: ChartParams) -> dict[str, Any]:
    """Posting time: weekday × hour of the source Telegram posts (Asia/Tashkent)."""
    grid: dict[tuple[int, int], int] = defaultdict(int)
    for stat in _stats(params, params.institutions()):
        for hour, n in enumerate(stat.by_hour or []):
            grid[(stat.date.weekday(), hour)] += n
    data = [[hour, wd, grid.get((wd, hour), 0)] for wd in range(7) for hour in range(24)]
    return {
        "kind": "heatmap",
        "xLabels": [f"{h:02d}" for h in range(24)],
        "yLabels": list(WEEKDAYS),
        "max": max(grid.values(), default=0) or 1,
        "series": [{"name": _("Xabarlar"), "data": data}],
        "table": {
            "columns": [_("Kun"), *[f"{h:02d}" for h in range(24)]],
            "rows": [[WEEKDAYS[wd], *[grid.get((wd, h), 0) for h in range(24)]] for wd in range(7)],
        },
    }


def engagement(params: ChartParams) -> dict[str, Any]:
    """Average Telegram views (or forwards) per post per institution — two measures, two charts."""
    institutions = params.institutions()
    forwards = params.metric == "forwards"
    sums: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for stat in _stats(params, institutions):
        sums[stat.institution_id][0] += stat.tg_forwards_sum if forwards else stat.tg_views_sum
        sums[stat.institution_id][1] += stat.posts
    by_inst = {pk: round(total / posts) if posts else 0 for pk, (total, posts) in sums.items()}
    data = [{"value": by_inst.get(i.pk, 0), "itemStyle": {"color": i.color}} for i in institutions]
    label = _("Oʻrtacha ulashishlar") if forwards else _("Oʻrtacha koʻrishlar")
    return {
        "kind": "bar",
        "categories": [i.abbreviation for i in institutions],
        "series": [{"name": label, "data": data}],
        "table": {
            "columns": [_("Muassasa"), label],
            "rows": [[i.short_name, by_inst.get(i.pk, 0)] for i in institutions],
        },
    }


def tags(params: ChartParams) -> dict[str, Any]:
    """Top 15 tags for the period, with the change against the previous period of the same length."""
    now = timezone.now()
    span = timedelta(days=params.days)
    published = Q(articles__status=ArticleStatus.PUBLISHED)
    current = Q(articles__published_at__gte=now - span) & published
    previous = (
        Q(articles__published_at__gte=now - 2 * span, articles__published_at__lt=now - span) & published
    )
    rows = list(
        Tag.objects.annotate(n=Count("articles", filter=current), prev=Count("articles", filter=previous))
        .filter(n__gt=0)
        .order_by("-n", "name")[:15]
    )
    return {
        "kind": "hbar",
        "categories": [t.name for t in rows],
        "series": [{"name": _("Maqolalar"), "data": [t.n for t in rows]}],
        "table": {
            "columns": [_("Teg"), _("Maqolalar"), _("Oldingi davr"), _("Oʻzgarish")],
            "rows": [[t.name, t.n, t.prev, f"{t.n - t.prev:+d}"] for t in rows],
        },
    }


def _latest_metrics() -> dict[tuple[int, str], dict[int, int | None]]:
    values: dict[tuple[int, str], dict[int, int | None]] = defaultdict(dict)
    for m in InstitutionMetric.objects.filter(institution__is_active=True).only(
        "institution_id", "key", "year", "value"
    ):
        values[(m.institution_id, m.key)][m.year] = m.value
    return values


def compare(params: ChartParams) -> dict[str, Any]:
    """One metric, grouped bars: years × institutions (one chart per metric — never dual axes)."""
    metric = params.metric if params.metric in MetricKey.values else MetricKey.STUDENTS
    institutions = params.institutions()
    values = _latest_metrics()
    years = sorted({y for (_i, key), by_year in values.items() if key == metric for y in by_year})[-4:]
    series = [
        {"name": i.abbreviation, "color": i.color, "data": [values[(i.pk, metric)].get(y) for y in years]}
        for i in institutions
    ]
    return {
        "kind": "grouped",
        "categories": [str(y) for y in years],
        "series": series,
        "table": {
            "columns": [_("Yil"), *[s["name"] for s in series]],
            "rows": [[str(y), *[s["data"][n] for s in series]] for n, y in enumerate(years)],
        },
    }


def radar(params: ChartParams) -> dict[str, Any]:
    """Normalised indicators (latest year, share of the best institution = 100)."""
    institutions = params.institutions()
    values = _latest_metrics()
    keys = [k for k in MetricKey.values if any(values.get((i.pk, k)) for i in institutions)]
    latest = {
        (i.pk, k): (values[(i.pk, k)][max(values[(i.pk, k)])] if values.get((i.pk, k)) else None)
        for i in institutions
        for k in keys
    }
    best = {k: max((latest[(i.pk, k)] or 0) for i in institutions) or 1 for k in keys}
    labels = [str(MetricKey(k).label) for k in keys]
    series = [
        {
            "name": i.abbreviation,
            "color": i.color,
            "data": [round(100 * (latest[(i.pk, k)] or 0) / best[k]) for k in keys],
        }
        for i in institutions
    ]
    return {
        "kind": "radar",
        "categories": labels,
        "series": series,
        "table": {
            "columns": [_("Koʻrsatkich"), *[i.abbreviation for i in institutions]],
            "rows": [[labels[n], *[latest[(i.pk, k)] for i in institutions]] for n, k in enumerate(keys)],
        },
    }


CHARTS: dict[str, Callable[[ChartParams], dict[str, Any]]] = {
    "activity": activity,
    "categories": categories,
    "heatmap": heatmap,
    "engagement": engagement,
    "tags": tags,
    "compare": compare,
    "radar": radar,
}


def to_csv(payload: dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(payload["table"]["columns"])
    for row in payload["table"]["rows"]:
        writer.writerow(["" if cell is None else cell for cell in row])
    return buffer.getvalue()
