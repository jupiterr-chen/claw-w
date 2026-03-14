from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

import requests


class StorageManager:
    """文件持久化管理器。"""

    def __init__(self, base_dir: str, organize_by_uid: bool = False):
        self.base_dir = Path(base_dir)
        self.organize_by_uid = organize_by_uid
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _date_dir(self, created_ts: int, user_id: str | None = None) -> Path:
        d = datetime.fromtimestamp(created_ts).strftime("%Y-%m-%d")
        path = self.base_dir / d
        if self.organize_by_uid and user_id:
            path = path / f"UID_{user_id}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _post_dir_name(created_ts: int, short_id: str) -> str:
        t = datetime.fromtimestamp(created_ts).strftime("%H%M%S")
        return f"Post_{t}_{short_id}"

    def save_post(self, post: Dict[str, Any], download_images: bool = True, image_timeout: int = 15) -> Dict[str, Any]:
        created_ts = int(post["created_ts"])
        short_id = str(post["id"])[-8:]

        user_id = str(post.get("user_id", "")).strip()
        date_dir = self._date_dir(created_ts, user_id=user_id)
        post_dir = date_dir / self._post_dir_name(created_ts, short_id)
        post_dir.mkdir(parents=True, exist_ok=True)

        # 正文
        (post_dir / "content.txt").write_text(post.get("text", ""), encoding="utf-8")

        saved = 0
        pics: List[str] = post.get("pics", [])
        if download_images and pics:
            # 使用线程池并发下载图片，最多同时下载3张
            with ThreadPoolExecutor(max_workers=3) as executor:
                future_to_url = {
                    executor.submit(self._download_image, url, post_dir / f"img_{i}.jpg", image_timeout):
                    url for i, url in enumerate(pics, start=1)
                }
                for future in as_completed(future_to_url):
                    if future.result():
                        saved += 1

        return {
            "date_dir": str(date_dir),
            "post_dir": str(post_dir),
            "post_id": str(post["id"]),
            "images_total": len(pics),
            "images_saved": saved,
        }

    def write_summary(self, date_dir: str, summary: Dict[str, Any]):
        path = Path(date_dir) / "summary.json"
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    def append_jsonl(self, relative_path: str, row: Dict[str, Any]):
        p = self.base_dir / relative_path
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    @staticmethod
    def file_sha256(path: str | Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _download_image(url: str, path: Path, timeout: int = 15) -> bool:
        try:
            r = requests.get(url, timeout=timeout, stream=True)
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception:
            return False
