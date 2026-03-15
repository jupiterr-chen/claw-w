from pathlib import Path

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
    assert result["source_post_id"] == "1234567890"
    assert result["post_id"].isdigit()
    assert len(result["post_id"]) == 20  # YYYYmmddHHMMSS + 6位序列号
    assert result["post_id"].startswith("20231115061320")


def test_reprocess_can_use_existing_images_without_downloading(tmp_path):
    s = StorageManager(str(tmp_path))
    post = {
        "id": "1234567890",
        "created_ts": 1700000000,
        "text": "hello world",
        "pics": ["https://example.com/a.jpg"],
    }

    local_post_id = s._generate_local_post_id(post["id"], post["created_ts"])
    img_dir = Path(tmp_path) / "raw" / "images" / local_post_id
    img_dir.mkdir(parents=True, exist_ok=True)
    existing = img_dir / "img_1.jpg"
    existing.write_bytes(b"fake")

    result = s.save_post(post, download_images=False)
    assert result["images_saved"] == 0
    assert str(existing) in result["image_paths"]
