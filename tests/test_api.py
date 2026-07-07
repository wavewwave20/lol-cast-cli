from datetime import datetime, timezone

from lolcast.api import align_ts


def test_align_ts_floors_to_10s():
    dt = datetime(2026, 7, 6, 6, 25, 7, 500000, tzinfo=timezone.utc)
    assert align_ts(dt) == "2026-07-06T06:25:00Z"


def test_align_ts_exact_boundary():
    dt = datetime(2026, 7, 6, 6, 25, 10, tzinfo=timezone.utc)
    assert align_ts(dt) == "2026-07-06T06:25:10Z"
