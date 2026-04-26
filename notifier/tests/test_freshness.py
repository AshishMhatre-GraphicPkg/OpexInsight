from datetime import datetime, timedelta, timezone

import pytest

from src.freshness import StaleDataError, assert_fresh


def _utcnow():
    return datetime.now(timezone.utc)


def test_fresh_file_does_not_raise():
    mtime = _utcnow() - timedelta(hours=1)
    assert_fresh(mtime, max_age_hours=24)


def test_stale_file_raises():
    mtime = _utcnow() - timedelta(hours=25)
    with pytest.raises(StaleDataError):
        assert_fresh(mtime, max_age_hours=24)


def test_exactly_at_boundary_raises():
    # strictly greater than max_age — the boundary itself is stale
    mtime = _utcnow() - timedelta(hours=24, seconds=1)
    with pytest.raises(StaleDataError):
        assert_fresh(mtime, max_age_hours=24)


def test_custom_max_age():
    mtime = _utcnow() - timedelta(hours=2)
    assert_fresh(mtime, max_age_hours=3)
    with pytest.raises(StaleDataError):
        assert_fresh(mtime, max_age_hours=1)
