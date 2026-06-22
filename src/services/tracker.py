import hashlib
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

from src.config.settings import DATABASE_PATH, TRACKER_BASE_URL


class ClickTracker:
    def __init__(self, db_path: Path | None = None) -> None:
        self._conn = sqlite3.connect(db_path or DATABASE_PATH, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS tracked_links (
                deal_id       TEXT PRIMARY KEY,
                affiliate_url TEXT NOT NULL,
                created_at    TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS clicks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_id    TEXT    NOT NULL,
                source     TEXT    NOT NULL DEFAULT '',
                clicked_at TEXT    NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_clicks_deal ON clicks(deal_id);
        """)
        self._conn.commit()

    def register(self, affiliate_url: str) -> str:
        """Registra o link afiliado e retorna a URL de rastreamento.
        Retorna string vazia se TRACKER_BASE_URL não estiver configurado."""
        if not TRACKER_BASE_URL or not affiliate_url:
            return ""
        deal_id = hashlib.sha256(affiliate_url.encode()).hexdigest()[:12]
        self._conn.execute(
            "INSERT OR IGNORE INTO tracked_links (deal_id, affiliate_url, created_at) VALUES (?, ?, ?)",
            (deal_id, affiliate_url, datetime.now(UTC).isoformat()),
        )
        self._conn.commit()
        return f"{TRACKER_BASE_URL}/{deal_id}"

    def get_affiliate_url(self, deal_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT affiliate_url FROM tracked_links WHERE deal_id = ?", (deal_id,)
        ).fetchone()
        return row[0] if row else None

    def log_click(self, deal_id: str, source: str) -> None:
        self._conn.execute(
            "INSERT INTO clicks (deal_id, source, clicked_at) VALUES (?, ?, ?)",
            (deal_id, source or "unknown", datetime.now(UTC).isoformat()),
        )
        self._conn.commit()

    def get_stats(self) -> list[dict]:
        rows = self._conn.execute("""
            SELECT t.deal_id, t.affiliate_url, c.source, COUNT(*) AS clicks
            FROM clicks c
            JOIN tracked_links t ON t.deal_id = c.deal_id
            GROUP BY t.deal_id, c.source
            ORDER BY clicks DESC
        """).fetchall()
        return [{"deal_id": r[0], "url": r[1], "source": r[2], "clicks": r[3]} for r in rows]

    def close(self) -> None:
        self._conn.close()
