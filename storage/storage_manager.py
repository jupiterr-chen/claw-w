from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


class StorageManager:
    """文件持久化管理器。"""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _date_dir(self, created_ts: int) -> Path:
        d = datetime.fromtimestamp(created_ts).strftime("%Y-%m-%d")
        path = self.base_dir / d
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _post_dir_name(created_ts: int, short_id: str) -> str:
        t = datetime.fromtimestamp(created_ts).strftime("%H%M%S")
        return f"Post_{t}_{short_id}"

    def save_post(self, post: Dict[str, Any], download_images: bool = True, image_timeout: int = 15) -> Dict[str, Any]:
        created_ts = int(post["created_ts"])
        short_id = str(post["id"])[-8:]

        date_dir = self._date_dir(created_ts)
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
