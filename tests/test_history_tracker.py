from tracking.history_tracker import HistoryTracker


def test_tracker_basic(tmp_path):
    db = tmp_path / "history.db"
    t = HistoryTracker(str(db))

    assert t.is_processed("a") is False
    t.mark_processed("a", "u1", 100)
    assert t.is_processed("a") is True
    assert t.latest_ts("u1") == 100

    t.mark_processed("b", "u1", 99)
    assert t.latest_ts("u1") == 100
