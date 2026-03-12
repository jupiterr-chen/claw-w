from __future__ import annotations

import os
import sqlite3
from typing import Optional


class HistoryTracker:
    """增量抓取历史追踪器。"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_weibos (
                    post_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_ts INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_processed_user_ts ON processed_weibos(user_id, created_ts)"
            )

    def is_processed(self, post_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT 1 FROM processed_weibos WHERE post_id = ? LIMIT 1", (post_id,)
            )
            return cur.fetchone() is not None

    def mark_processed(self, post_id: str, user_id: str, created_ts: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO processed_weibos(post_id, user_id, created_ts) VALUES(?,?,?)",
                (post_id, user_id, created_ts),
            )

    def latest_ts(self, user_id: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT COALESCE(MAX(created_ts), 0) FROM processed_weibos WHERE user_id = ?",
                (user_id,),
            )
            return int(cur.fetchone()[0])
