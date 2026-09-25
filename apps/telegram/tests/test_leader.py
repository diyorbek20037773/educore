"""Leader lock and heartbeat semantics (FR-TG-9) against the isolated test Redis database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest import mock

import pytest
import redis

from apps.core.health import ingestor_heartbeat_age_seconds
from apps.telegram.ingestor.leader import LEADER_KEY, LeaderLock, LockState, write_heartbeat


def test_first_instance_owns_second_waits(redis_clean: Any) -> None:
    first = LeaderLock(redis_clean, owner="a:1")
    second = LeaderLock(redis_clean, owner="b:2")
    assert first.acquire() == LockState.OWNED
    assert second.acquire() == LockState.HELD_BY_OTHER
    assert first.renew() == LockState.OWNED
    assert second.renew() == LockState.HELD_BY_OTHER
    assert 0 < redis_clean.ttl(LEADER_KEY) <= 60


def test_release_only_by_owner(redis_clean: Any) -> None:
    first = LeaderLock(redis_clean, owner="a:1")
    first.acquire()
    LeaderLock(redis_clean, owner="b:2").release()
    assert redis_clean.get(LEADER_KEY) == "a:1"
    first.release()
    assert redis_clean.get(LEADER_KEY) is None
    assert LeaderLock(redis_clean, owner="b:2").acquire() == LockState.OWNED


def test_renew_reacquires_expired_key(redis_clean: Any) -> None:
    lock = LeaderLock(redis_clean, owner="a:1")
    lock.acquire()
    redis_clean.delete(LEADER_KEY)  # e.g. Redis restarted without AOF
    assert lock.renew() == LockState.OWNED
    assert redis_clean.get(LEADER_KEY) == "a:1"


def test_redis_errors_never_stop_the_ingestor() -> None:
    broken = mock.Mock(spec=redis.Redis)
    broken.set.side_effect = redis.ConnectionError("down")
    broken.eval.side_effect = redis.ConnectionError("down")
    broken.exists.side_effect = redis.ConnectionError("down")
    lock = LeaderLock(broken, owner="a:1")
    assert lock.acquire() == LockState.UNKNOWN
    assert lock.renew() == LockState.UNKNOWN
    assert lock.is_held_by_anyone() is None
    assert write_heartbeat(broken) is False


@pytest.mark.django_db
def test_heartbeat_age(redis_clean: Any) -> None:
    assert ingestor_heartbeat_age_seconds() is None
    write_heartbeat(redis_clean, datetime.now(UTC) - timedelta(seconds=100))
    age = ingestor_heartbeat_age_seconds()
    assert age is not None and 99 <= age < 110
