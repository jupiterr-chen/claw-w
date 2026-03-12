from storage.storage_manager import StorageManager


def test_save_post_without_images(tmp_path):
    s = StorageManager(str(tmp_path))
    post = {
        "id": "1234567890",
        "created_ts": 1700000000,
        "text": "hello world",
        "pics": ["https://example.com/a.jpg"],
    }

    result = s.save_post(post, download_images=False)
    assert result["images_saved"] == 0
    assert result["images_total"] == 1
