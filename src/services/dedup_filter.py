import hashlib
import sqlite3
from datetime import datetime, timedelta, UTC
from pathlib import Path

from loguru import logger

from src.config.settings import DATABASE_PATH, DEDUP_TTL_DAYS
from src.models import Deal


class DedupFilter:
    def __init__(self, db_path: Path | None = None) -> None:
        path = db_path or DATABASE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._create_table()
        self._purge_expired()

    def _create_table(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_deals (
                url_hash TEXT PRIMARY KEY,
                seen_at  TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def _hash(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()

    def is_new(self, deal: Deal) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM seen_deals WHERE url_hash = ?",
            (self._hash(deal.url),),
        )
        return cur.fetchone() is None

    def mark_seen(self, deal: Deal) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO seen_deals (url_hash, seen_at) VALUES (?, ?)",
            (self._hash(deal.url), datetime.now(UTC).isoformat()),
        )
        self._conn.commit()
        logger.debug("Marcado como visto: {}", deal.title[:60])

    def _purge_expired(self) -> None:
        cutoff = (datetime.now(UTC) - timedelta(days=DEDUP_TTL_DAYS)).isoformat()
        cur = self._conn.execute(
            "DELETE FROM seen_deals WHERE seen_at < ?", (cutoff,)
        )
        self._conn.commit()
        if cur.rowcount:
            logger.info("Dedup: {} registro(s) expirado(s) removido(s).", cur.rowcount)

    def close(self) -> None:
        self._conn.close()
