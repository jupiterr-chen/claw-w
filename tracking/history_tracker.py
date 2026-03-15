from __future__ import annotations

import os
import sqlite3
from typing import Optional


class HistoryTracker:
    """增量抓取历史追踪器。"""

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, col: str, decl: str):
        cur = conn.execute(f"PRAGMA table_info({table})")
        cols = {row[1] for row in cur.fetchall()}
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")

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
                    source_post_id TEXT UNIQUE,
                    user_id TEXT NOT NULL,
                    created_ts INTEGER NOT NULL
                )
                """
            )
            self._ensure_column(conn, "processed_weibos", "source_post_id", "TEXT")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_processed_user_ts ON processed_weibos(user_id, created_ts)"
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_processed_source_post_id ON processed_weibos(source_post_id)"
            )

    def is_processed(self, source_post_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                SELECT 1 FROM processed_weibos
                WHERE source_post_id = ? OR post_id = ?
                LIMIT 1
                """,
                (source_post_id, source_post_id),
            )
            return cur.fetchone() is not None

    def mark_processed(self, post_id: str, user_id: str, created_ts: int, source_post_id: Optional[str] = None):
        source_post_id = source_post_id or post_id
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO processed_weibos(post_id, source_post_id, user_id, created_ts)
                VALUES(?,?,?,?)
                """,
                (post_id, source_post_id, user_id, created_ts),
            )

    def latest_ts(self, user_id: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT COALESCE(MAX(created_ts), 0) FROM processed_weibos WHERE user_id = ?",
                (user_id,),
            )
            return int(cur.fetchone()[0])
