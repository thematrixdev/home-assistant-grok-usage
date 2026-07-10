"""Verify Grok usage parsing: explicit percentages and ISO reset times."""
import sys
import pathlib
from datetime import timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "custom_components"))

from hass_grok_usage import _as_percent, _parse_iso, _parse_usage  # noqa: E402


def test_as_percent():
    # Grok reports real percentages — no fraction scaling (8.0 stays 8, not 800).
    assert _as_percent(8.0) == 8.0
    assert _as_percent(0.5) == 0.5
    assert _as_percent(0) == 0.0
    assert _as_percent(100) == 100.0
    assert _as_percent("8%") == 8.0

    # Invalid
    assert _as_percent(-1) is None
    assert _as_percent(1001) is None
    assert _as_percent(True) is None
    assert _as_percent("bad") is None
    assert _as_percent(None) is None
    assert _as_percent(float("nan")) is None
    assert _as_percent(float("inf")) is None


def test_parse_iso():
    dt = _parse_iso("2026-07-16T01:29:34.782670+00:00")
    assert dt is not None and dt.tzinfo is not None
    naive = _parse_iso("2026-07-16T01:29:34")
    assert naive is not None and naive.tzinfo == timezone.utc
    assert _parse_iso("nope") is None
    assert _parse_iso(None) is None


def test_parse_usage():
    raw = {
        "config": {
            "currentPeriod": {
                "type": "USAGE_PERIOD_TYPE_WEEKLY",
                "end": "2026-07-16T01:29:34.782670+00:00",
            },
            "creditUsagePercent": 8.0,
        }
    }
    data = _parse_usage(raw)
    assert data["weekly_limit_percent"] == 8.0
    assert data["weekly_reset_time"].year == 2026
    assert _parse_usage({}) == {}


if __name__ == "__main__":
    test_as_percent()
    test_parse_iso()
    test_parse_usage()
    print("OK")
