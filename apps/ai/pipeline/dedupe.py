"""Cross-source duplicate detection (AI_PIPELINE §2.4): pgvector candidates, LLM confirm, attach/new."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import F, Q, Value
from django.db.models.functions import Greatest
from pgvector.django import CosineDistance

from apps.ai.models import EventCluster
from apps.telegram.models import TelegramPost

MAX_DISTANCE_OTHER_SOURCE = 0.14  # similarity ≥ 0.86
MAX_DISTANCE_SAME_SOURCE = 0.03  # similarity ≥ 0.97 (repost)
WINDOW = timedelta(hours=72)
CONFIRM_MIN_CONFIDENCE = 0.7


@dataclass(frozen=True)
class Candidate:
    post_id: int
    distance: float
    cluster_id: int | None
    article_id: int | None


def find_candidates(post: TelegramPost, embedding: list[float], limit: int = 5) -> list[Candidate]:
    """Nearest earlier posts from other sources (or near-identical reposts from the same source)."""
    qs = (
        TelegramPost.objects.exclude(pk=post.pk)
        .filter(
            is_deleted=False,
            embedding__isnull=False,
            published_at__gte=post.published_at - WINDOW,
            published_at__lte=post.published_at + WINDOW,
        )
        .annotate(distance=CosineDistance("embedding", embedding))
        .filter(
            Q(~Q(source_id=post.source_id), distance__lt=MAX_DISTANCE_OTHER_SOURCE)
            | Q(source_id=post.source_id, distance__lte=MAX_DISTANCE_SAME_SOURCE)
        )
        .select_related("cluster")
        .order_by("distance")[:limit]
    )
    return [
        Candidate(
            post_id=p.pk,
            distance=float(p.distance),
            cluster_id=p.cluster_id,
            article_id=p.cluster.canonical_article_id if p.cluster else None,
        )
        for p in qs
    ]


def new_cluster(post: TelegramPost, embedding: list[float], title: str) -> EventCluster:
    cluster = EventCluster.objects.create(
        title=title[:300],
        first_seen_at=post.published_at,
        last_seen_at=post.published_at,
        embedding=embedding,
        posts_count=1,
        sources_count=1,
    )
    TelegramPost.objects.filter(pk=post.pk).update(cluster=cluster)
    return cluster


def attach_to_cluster(post: TelegramPost, cluster_id: int) -> None:
    """Add a confirmed duplicate to an existing cluster and refresh its counters."""
    TelegramPost.objects.filter(pk=post.pk).update(cluster_id=cluster_id)
    sources = TelegramPost.objects.filter(cluster_id=cluster_id).values("source_id").distinct().count()
    EventCluster.objects.filter(pk=cluster_id).update(
        posts_count=F("posts_count") + 1,
        sources_count=sources,
        last_seen_at=Greatest(F("last_seen_at"), Value(post.published_at)),
    )
