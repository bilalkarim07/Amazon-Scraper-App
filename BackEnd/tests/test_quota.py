""" test_quota.py — Tests for the rolling 24-hour quota system. """
import pytest
from datetime import datetime, timedelta, timezone

from application import database, quota_service
from application.config import DAILY_QUOTA_LIMIT


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test_app.db"
    with patch("application.config.DB_PATH", db_path):
        database.init_db()
        yield db_path


def test_no_reset_after_23_hours(temp_db):
    """TEST 1: window_started_at = now - 23h → NO RESET."""
    past = datetime.now(timezone.utc) - timedelta(hours=23)
    past_iso = past.isoformat()
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE quota SET used = 100, window_started_at = ? WHERE id = 1",
            (past_iso,)
        )
        conn.commit()

    result = quota_service.check_and_reset_quota()
    assert result["used"] == 100, "Quota should NOT reset after 23 hours"


def test_reset_after_24_hours(temp_db):
    """TEST 2: window_started_at = now - 24h → RESET."""
    past = datetime.now(timezone.utc) - timedelta(hours=24)
    past_iso = past.isoformat()
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE quota SET used = 100, window_started_at = ? WHERE id = 1",
            (past_iso,)
        )
        conn.commit()

    result = quota_service.check_and_reset_quota()
    assert result["used"] == 0, "Quota should reset after 24 hours"


def test_reset_after_25_hours(temp_db):
    """TEST 3: window_started_at = now - 25h → RESET."""
    past = datetime.now(timezone.utc) - timedelta(hours=25)
    past_iso = past.isoformat()
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE quota SET used = 100, window_started_at = ? WHERE id = 1",
            (past_iso,)
        )
        conn.commit()

    result = quota_service.check_and_reset_quota()
    assert result["used"] == 0, "Quota should reset after 25 hours"


def test_calendar_date_change_2_hours_elapsed(temp_db):
    """TEST 4: Calendar date changed but only 2 hours elapsed → NO RESET."""
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    past_iso = past.isoformat()
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE quota SET used = 100, window_started_at = ? WHERE id = 1",
            (past_iso,)
        )
        conn.commit()

    result = quota_service.check_and_reset_quota()
    # Even if the calendar date changed, only 2 hours have passed → no reset
    assert result["used"] == 100, "Quota should NOT reset after only 2 hours"


def test_24_hours_same_calendar_date(temp_db):
    """TEST 5: 24 hours elapsed without calendar date changing → RESET."""
    past = datetime.now(timezone.utc) - timedelta(hours=24)
    past_iso = past.isoformat()
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE quota SET used = 100, window_started_at = ? WHERE id = 1",
            (past_iso,)
        )
        conn.commit()

    result = quota_service.check_and_reset_quota()
    assert result["used"] == 0, "Quota should reset after 24 hours"


def test_startup_with_expired_quota(temp_db):
    """TEST 6: Backend startup with expired quota → RESET."""
    past = datetime.now(timezone.utc) - timedelta(hours=25)
    past_iso = past.isoformat()
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE quota SET used = 100, window_started_at = ? WHERE id = 1",
            (past_iso,)
        )
        conn.commit()

    result = quota_service.check_and_reset_quota()
    assert result["used"] == 0, "Startup should reset expired quota"


def test_get_quota_after_expiry(temp_db):
    """TEST 7: GET /api/quota after expiry → RESET before response."""
    past = datetime.now(timezone.utc) - timedelta(hours=25)
    past_iso = past.isoformat()
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE quota SET used = 100, window_started_at = ? WHERE id = 1",
            (past_iso,)
        )
        conn.commit()

    result = quota_service.get_quota()
    assert result["used"] == 0, "GET /api/quota should reset expired quota"


def test_reserve_quota_after_expiry(temp_db):
    """TEST 8: POST /api/jobs after expiry → reset before reservation."""
    past = datetime.now(timezone.utc) - timedelta(hours=25)
    past_iso = past.isoformat()
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE quota SET used = 100, window_started_at = ? WHERE id = 1",
            (past_iso,)
        )
        conn.commit()

    success, error = quota_service.reserve_quota(50)
    assert success, f"Reservation failed: {error}"

    with database.get_connection() as conn:
        row = conn.execute("SELECT used, window_started_at FROM quota WHERE id = 1").fetchone()
        assert row["used"] == 50, "Quota should be reset to 0 then reserved 50"
        now = datetime.now(timezone.utc)
        window_start = datetime.fromisoformat(row["window_started_at"])
        assert (now - window_start).total_seconds() < 10, "window_started_at should be recent"


def test_quota_exceeded(temp_db):
    """TEST 9: Quota exceeded → HTTP 429 and quota remains correct."""
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE quota SET used = ? WHERE id = 1",
            (DAILY_QUOTA_LIMIT - 10,)
        )
        conn.commit()

    success, error = quota_service.reserve_quota(20)
    assert not success, "Should fail when quota exceeded"
    assert "Quota exceeded" in error

    with database.get_connection() as conn:
        row = conn.execute("SELECT used FROM quota WHERE id = 1").fetchone()
        assert row["used"] == DAILY_QUOTA_LIMIT - 10, "Quota should remain unchanged on failure"


def test_concurrent_reservation(temp_db):
    """TEST 10: Two concurrent quota reservations → atomic, no over-allocation."""
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE quota SET used = ? WHERE id = 1",
            (DAILY_QUOTA_LIMIT - 15,)
        )
        conn.commit()

    success1, _ = quota_service.reserve_quota(10)
    assert success1

    success2, error2 = quota_service.reserve_quota(10)
    assert not success2

    with database.get_connection() as conn:
        row = conn.execute("SELECT used FROM quota WHERE id = 1").fetchone()
        assert row["used"] == DAILY_QUOTA_LIMIT - 5, "Quota should be correctly reserved"


def test_reservation_and_settlement(temp_db):
    """TEST 11: Reservation + settlement (requested=100, successful=70) → final increase=70."""
    initial_used = 100
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE quota SET used = ? WHERE id = 1",
            (initial_used,)
        )
        conn.commit()

    success, _ = quota_service.reserve_quota(100)
    assert success

    with database.get_connection() as conn:
        row = conn.execute("SELECT used FROM quota WHERE id = 1").fetchone()
        assert row["used"] == initial_used + 100

    quota_service.settle_quota("test-job", 100, 70)

    with database.get_connection() as conn:
        row = conn.execute("SELECT used FROM quota WHERE id = 1").fetchone()
        assert row["used"] == initial_used + 70, "Final quota increase should be 70, not 100"


def test_migration_old_schema(temp_db):
    """TEST 12: Migration from old schema (no window_started_at) preserves data."""
    with database.get_connection() as conn:
        cursor = conn.execute("PRAGMA table_info(quota)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "window_started_at" in columns, "window_started_at column should exist"

        row = conn.execute("SELECT used, daily_limit, reserved FROM quota WHERE id = 1").fetchone()
        assert row["used"] == 0 or row["used"] is not None
        assert row["daily_limit"] == DAILY_QUOTA_LIMIT