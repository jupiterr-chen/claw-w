#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def gen_local_post_id(source_post_id: str, created_ts: int) -> str:
    dt = datetime.fromtimestamp(int(created_ts)).strftime("%Y%m%d%H%M%S")
    digits = "".join(ch for ch in str(source_post_id) if ch.isdigit())
    if digits:
        seq = int(digits[-12:]) % 1_000_000
    else:
        seq = int(hashlib.sha1(str(source_post_id).encode("utf-8")).hexdigest()[:8], 16) % 1_000_000
    return f"{dt}{seq:06d}"


def is_new_format(post_id: str) -> bool:
    return len(post_id) == 20 and post_id.isdigit()


def load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    rows = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def dump_jsonl(p: Path, rows: list[dict]):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description="迁移旧 post_id 到 YYYYmmddHHMMSS+6位序列号")
    ap.add_argument("--base-dir", default="./weibo_data")
    ap.add_argument("--apply", action="store_true", help="真正执行迁移（默认 dry-run）")
    args = ap.parse_args()

    base = Path(args.base_dir)
    db_path = base / "history.db"
    images_dir = base / "raw" / "images"

    if not db_path.exists():
        raise SystemExit(f"history.db 不存在: {db_path}")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cols = {r[1] for r in conn.execute("PRAGMA table_info(processed_weibos)").fetchall()}
        if "source_post_id" not in cols and args.apply:
            conn.execute("ALTER TABLE processed_weibos ADD COLUMN source_post_id TEXT")

        rows = conn.execute(
            "SELECT post_id, COALESCE(source_post_id, post_id) AS source_post_id, user_id, created_ts FROM processed_weibos"
        ).fetchall()

        mapping: dict[str, str] = {}
        used_new_ids = {r["post_id"] for r in rows if is_new_format(str(r["post_id"]))}

        for r in rows:
            old_post_id = str(r["post_id"])
            src_id = str(r["source_post_id"])
            created_ts = int(r["created_ts"])
            if is_new_format(old_post_id):
                continue

            new_id = gen_local_post_id(src_id, created_ts)
            while new_id in used_new_ids and mapping.get(old_post_id) != new_id:
                seq = (int(new_id[-6:]) + 1) % 1_000_000
                new_id = f"{new_id[:-6]}{seq:06d}"
            used_new_ids.add(new_id)
            mapping[old_post_id] = new_id

        print(f"[plan] 需要迁移 {len(mapping)} 条 post_id")

        # 1) 目录迁移
        moved = 0
        for old_id, new_id in mapping.items():
            old_dir = images_dir / old_id
            new_dir = images_dir / new_id
            if not old_dir.exists():
                continue
            print(f"[dir] {old_dir} -> {new_dir}")
            if args.apply:
                new_dir.parent.mkdir(parents=True, exist_ok=True)
                if new_dir.exists():
                    for p in old_dir.iterdir():
                        target = new_dir / p.name
                        if not target.exists():
                            shutil.move(str(p), str(target))
                    if old_dir.exists() and not any(old_dir.iterdir()):
                        old_dir.rmdir()
                else:
                    shutil.move(str(old_dir), str(new_dir))
            moved += 1

        # 2) history.db 迁移
        for old_id, new_id in mapping.items():
            print(f"[db] {old_id} -> {new_id}")
            if args.apply:
                row = conn.execute(
                    "SELECT user_id, created_ts FROM processed_weibos WHERE post_id=?", (old_id,)
                ).fetchone()
                if not row:
                    continue
                conn.execute("DELETE FROM processed_weibos WHERE post_id=?", (old_id,))
                conn.execute(
                    "INSERT OR REPLACE INTO processed_weibos(post_id, source_post_id, user_id, created_ts) VALUES(?,?,?,?)",
                    (new_id, old_id, row["user_id"], int(row["created_ts"])),
                )

        # 3) JSONL 迁移
        def remap_path(path_str: str, old_id: str, new_id: str) -> str:
            return path_str.replace(f"/images/{old_id}/", f"/images/{new_id}/")

        posts = load_jsonl(base / "raw" / "posts.jsonl")
        for r in posts:
            pid = str(r.get("post_id", ""))
            if pid in mapping:
                new_id = mapping[pid]
                r["source_post_id"] = pid
                r["post_id"] = new_id
                r["image_paths"] = [remap_path(p, pid, new_id) for p in r.get("image_paths", [])]
        if args.apply:
            dump_jsonl(base / "raw" / "posts.jsonl", posts)

        ocr = load_jsonl(base / "raw" / "ocr.jsonl")
        for r in ocr:
            pid = str(r.get("post_id", ""))
            if pid in mapping:
                new_id = mapping[pid]
                r["source_post_id"] = pid
                r["post_id"] = new_id
                if isinstance(r.get("image"), str):
                    r["image"] = remap_path(r["image"], pid, new_id)
        if args.apply:
            dump_jsonl(base / "raw" / "ocr.jsonl", ocr)

        signals = load_jsonl(base / "curated" / "signals.jsonl")
        for r in signals:
            spid = str(r.get("source_post_id", ""))
            if spid in mapping:
                r["local_post_id"] = mapping[spid]
        if args.apply:
            dump_jsonl(base / "curated" / "signals.jsonl", signals)

        if args.apply:
            conn.commit()

    print(f"[done] {'已执行' if args.apply else 'dry-run 完成'}")


if __name__ == "__main__":
    main()
