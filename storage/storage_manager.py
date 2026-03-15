from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from storage.download_utils import download_batch


class StorageManager:
    """文件持久化管理器（Raw + Curated 两层）。"""

    @staticmethod
    def _collect_existing_images(image_dir: Path) -> List[str]:
        if not image_dir.exists():
            return []
        exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        return sorted(str(p) for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in exts)

    @staticmethod
    def _generate_local_post_id(source_post_id: str, created_ts: int) -> str:
        """生成本地稳定 ID: YYYYmmddHHMMSS + 6位序列号。"""
        dt = datetime.fromtimestamp(int(created_ts)).strftime("%Y%m%d%H%M%S")
        digits = "".join(ch for ch in str(source_post_id) if ch.isdigit())
        if digits:
            seq = int(digits[-12:]) % 1_000_000
        else:
            seq = int(hashlib.sha1(str(source_post_id).encode("utf-8")).hexdigest()[:8], 16) % 1_000_000
        return f"{dt}{seq:06d}"

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
        source_post_id = str(post["id"])
        post_id = self._generate_local_post_id(source_post_id, int(post.get("created_ts", 0)))
        post_image_dir = self.images_dir / post_id
        post_image_dir.mkdir(parents=True, exist_ok=True)

        saved = 0
        pics: List[str] = post.get("pics", [])
        image_paths: List[str] = []

        if download_images and pics:
            tasks = [(url, post_image_dir / f"img_{i}.jpg") for i, url in enumerate(pics, start=1)]
            dl_result = download_batch(tasks, max_workers=3, timeout=image_timeout)
            saved = dl_result["success"]
            image_paths = sorted([d["path"] for d in dl_result["details"] if d["ok"]])
        elif pics:
            image_paths = self._collect_existing_images(post_image_dir)

        # raw/posts.jsonl：保真原始微博数据 + 本地落盘路径
        if append_post_row:
            raw_post_row = {
                "post_id": post_id,
                "source_post_id": source_post_id,
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
            "source_post_id": source_post_id,
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

