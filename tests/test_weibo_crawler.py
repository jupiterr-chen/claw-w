from crawler.weibo_crawler import WeiboCrawler


def test_extract_pic_and_text_cleanup():
    c = WeiboCrawler(cookie="x", user_agent="ua", delay_min=0, delay_max=0)
    mblog = {
        "id": "1",
        "created_at": "今天 10:00",
        "text": "hello<br/>world",
        "user": {"id": "u1"},
        "pics": [{"large": {"url": "https://img/a.jpg"}}],
    }
    data = {"data": {"cards": [{"card_type": 9, "mblog": mblog}]}}
    parsed = c.parse_cards(data)
    assert len(parsed) == 1
    assert parsed[0]["text"] == "hello\nworld"
    assert parsed[0]["pics"] == ["https://img/a.jpg"]
