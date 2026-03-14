from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


class StorageManager:
    """文件持久化管理器（Raw + Curated 两层）。"""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.raw_dir = self.base_dir / "raw"
        self.curated_dir = self.base_dir / "curated"
        self.images_dir = self.raw_dir / "images"

        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.curated_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def save_post(
        self,
        post: Dict[str, Any],
        download_images: bool = True,
        image_timeout: int = 15,
        append_post_row: bool = True,
    ) -> Dict[str, Any]:
        post_id = str(post["id"])
        post_image_dir = self.images_dir / post_id
        post_image_dir.mkdir(parents=True, exist_ok=True)

        saved = 0
        pics: List[str] = post.get("pics", [])
        image_paths: List[str] = []

        if download_images and pics:
            with ThreadPoolExecutor(max_workers=3) as executor:
                future_to_path = {
                    executor.submit(self._download_image, url, post_image_dir / f"img_{i}.jpg", image_timeout):
                    (url, post_image_dir / f"img_{i}.jpg") for i, url in enumerate(pics, start=1)
                }
                for future in as_completed(future_to_path):
                    _, out_path = future_to_path[future]
                    if future.result():
                        saved += 1
                        image_paths.append(str(out_path))

        # raw/posts.jsonl：保真原始微博数据 + 本地落盘路径
        if append_post_row:
            raw_post_row = {
                "post_id": post_id,
                "user_id": post.get("user_id"),
                "created_ts": post.get("created_ts"),
                "created_at": post.get("created_at"),
                "text": post.get("text", ""),
                "pics": pics,
                "source": post.get("source", ""),
                "images_saved": saved,
                "image_paths": sorted(image_paths),
            }
            self.append_jsonl("raw/posts.jsonl", raw_post_row)

        return {
            "post_id": post_id,
            "images_total": len(pics),
            "images_saved": saved,
            "image_paths": sorted(image_paths),
            "image_dir": str(post_image_dir),
        }

    def append_jsonl(self, relative_path: str, row: Dict[str, Any]):
        p = self.base_dir / relative_path
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def write_daily_summary(self, date_key: str, lines: List[str]):
        p = self.curated_dir / "daily_summary.md"
        content = "\n".join(lines).rstrip() + "\n"
        p.write_text(content, encoding="utf-8")

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
