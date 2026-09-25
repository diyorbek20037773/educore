"""Chart payloads for `/analitika/data/<chart>/` (SPEC §6.9, §7.4).

Every builder returns the `charts.js` contract: `kind`, `categories`, `series` (institution series carry the
fixed palette colour from `Institution.color`, ADR-007) and a `table` used for the table view and CSV.
Phase 5 swaps the live aggregates for `InstitutionDailyStat` rollups; the payload shape stays the same.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from django.db.models import Avg, Count, Q, QuerySet
from django.db.models.functions import ExtractHour, ExtractIsoWeekDay, TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.content.models import Article, ArticleStatus, Category, Tag
from apps.institutions.models import Institution, InstitutionMetric, MetricKey
from apps.telegram.models import TelegramPost

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


def _published(params: ChartParams) -> QuerySet[Article]:
    return Article.objects.filter(status=ArticleStatus.PUBLISHED, published_at__gte=params.since)


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


def activity(params: ChartParams) -> dict[str, Any]:
    """Articles per institution over time — one line per institution, fixed colours."""
    institutions = params.institutions()
    periods = _periods(params)
    trunc = TruncMonth if params.monthly else (TruncWeek if params.days > 90 else TruncDate)
    rows = (
        _published(params)
        .filter(primary_institution__in=institutions)
        .annotate(bucket=trunc("published_at"))
        .order_by()
        .values("primary_institution", "bucket")
        .annotate(n=Count("id"))
    )
    counts: dict[int, dict[date, int]] = defaultdict(dict)
    for row in rows:
        bucket = row["bucket"]
        counts[row["primary_institution"]][bucket.date() if hasattr(bucket, "date") else bucket] = row["n"]
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
    """Articles by category — horizontal bars in a single hue."""
    qs = _published(params)
    if params.institution_slugs:
        qs = qs.filter(institutions__slug__in=params.institution_slugs).distinct()
    rows = qs.order_by().values("category").annotate(n=Count("id", distinct=True)).order_by("-n")
    names = dict(Category.objects.values_list("pk", "name"))
    data = [(names.get(r["category"], _("Boshqa")), r["n"]) for r in rows]
    return {
        "kind": "hbar",
        "categories": [d[0] for d in data],
        "series": [{"name": _("Maqolalar"), "data": [d[1] for d in data]}],
        "table": {"columns": [_("Kategoriya"), _("Maqolalar")], "rows": [list(d) for d in data]},
    }


def heatmap(params: ChartParams) -> dict[str, Any]:
    """Posting time: weekday × hour of the source Telegram posts (local time)."""
    qs = TelegramPost.objects.filter(published_at__gte=params.since, is_deleted=False)
    if params.institution_slugs:
        qs = qs.filter(source__institution__slug__in=params.institution_slugs)
    tz = timezone.get_current_timezone()
    rows = (
        qs.annotate(
            wd=ExtractIsoWeekDay("published_at", tzinfo=tz), hour=ExtractHour("published_at", tzinfo=tz)
        )
        .order_by()
        .values("wd", "hour")
        .annotate(n=Count("id"))
    )
    grid = {(r["wd"] - 1, r["hour"]): r["n"] for r in rows}
    data = [[hour, wd, grid.get((wd, hour), 0)] for wd in range(7) for hour in range(24)]
    return {
        "kind": "heatmap",
        "xLabels": [f"{h:02d}" for h in range(24)],
        "yLabels": list(WEEKDAYS),
        "max": max(grid.values(), default=1),
        "series": [{"name": _("Xabarlar"), "data": data}],
        "table": {
            "columns": [_("Kun"), *[f"{h:02d}" for h in range(24)]],
            "rows": [[WEEKDAYS[wd], *[grid.get((wd, h), 0) for h in range(24)]] for wd in range(7)],
        },
    }


def engagement(params: ChartParams) -> dict[str, Any]:
    """Average Telegram views per post per institution (forwards are a separate chart — no dual axes)."""
    institutions = params.institutions()
    measure = "forwards" if params.metric == "forwards" else "views"
    rows = (
        TelegramPost.objects.filter(
            published_at__gte=params.since, is_deleted=False, **{f"{measure}__isnull": False}
        )
        .order_by()
        .values("source__institution")
        .annotate(avg=Avg(measure))
    )
    by_inst = {r["source__institution"]: round(r["avg"] or 0) for r in rows}
    data = [{"value": by_inst.get(i.pk, 0), "itemStyle": {"color": i.color}} for i in institutions]
    label = _("Oʻrtacha koʻrishlar") if measure == "views" else _("Oʻrtacha ulashishlar")
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
