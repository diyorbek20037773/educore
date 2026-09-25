"""Editorial operations used by admin actions (SPEC §8 › Tahririyat)."""

from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction
from django.utils import timezone

from apps.content.models import Article, ArticleSource, ArticleStatus
from apps.core.cache import bump_content_version


@transaction.atomic
def merge_articles(target: Article, duplicates: Iterable[Article]) -> int:
    """Move every source of `duplicates` onto `target`, archive the duplicates, flag `target` for a refresh.

    Returns the number of sources moved. The caller schedules the regeneration (`ai.regenerate_article`).
    """
    moved = 0
    for duplicate in duplicates:
        if duplicate.pk == target.pk:
            continue
        moved += ArticleSource.objects.filter(article=duplicate).update(article=target, is_primary=False)
        target.institutions.add(*duplicate.institutions.all())
        duplicate.status = ArticleStatus.ARCHIVED
        duplicate.review_reason = f"merged_into:{target.pk}"
        duplicate.save(update_fields=["status", "review_reason", "updated_at"])
        if duplicate.cluster_id and not target.cluster_id:
            target.cluster_id = duplicate.cluster_id
    target.needs_refresh = True
    target.edited_at = timezone.now()
    target.save(update_fields=["needs_refresh", "cluster", "edited_at", "updated_at"])
    transaction.on_commit(bump_content_version)
    return moved
