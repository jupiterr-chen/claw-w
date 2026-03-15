from main import _next_consecutive_processed


def test_next_consecutive_processed_normal_mode():
    consecutive = 0
    for _ in range(10):
        consecutive = _next_consecutive_processed(
            consecutive_processed=consecutive,
            already_processed=True,
            reprocess_ocr=False,
        )
    assert consecutive == 10


def test_next_consecutive_processed_resets_on_new_post():
    consecutive = 5
    consecutive = _next_consecutive_processed(
        consecutive_processed=consecutive,
        already_processed=False,
        reprocess_ocr=False,
    )
    assert consecutive == 0


def test_next_consecutive_processed_reprocess_mode_always_zero():
    consecutive = 7
    consecutive = _next_consecutive_processed(
        consecutive_processed=consecutive,
        already_processed=True,
        reprocess_ocr=True,
    )
    assert consecutive == 0
