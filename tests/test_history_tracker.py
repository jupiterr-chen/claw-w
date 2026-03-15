from tracking.history_tracker import HistoryTracker


def test_tracker_basic(tmp_path):
    db = tmp_path / "history.db"
    t = HistoryTracker(str(db))

    assert t.is_processed("wbid_a") is False
    t.mark_processed("20260101130000123456", "u1", 100, source_post_id="wbid_a")
    assert t.is_processed("wbid_a") is True
    assert t.latest_ts("u1") == 100

    t.mark_processed("20260101130100123457", "u1", 99, source_post_id="wbid_b")
    assert t.latest_ts("u1") == 100
