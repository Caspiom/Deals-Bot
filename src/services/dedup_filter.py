import hashlib
import sqlite3
from datetime import datetime, timedelta, UTC
from pathlib import Path

from loguru import logger

from src.config.settings import (
    DATABASE_PATH,
    DEDUP_TTL_DAYS,
    MIN_HOT_DISCOUNT_PCT,
    REPOST_INTERVAL_HOURS,
)
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
                url_hash       TEXT PRIMARY KEY,
                seen_at        TEXT NOT NULL,
                last_posted_at TEXT NOT NULL
            )
        """)
        # migração para DBs existentes sem last_posted_at
        try:
            self._conn.execute("ALTER TABLE seen_deals ADD COLUMN last_posted_at TEXT")
            self._conn.execute("UPDATE seen_deals SET last_posted_at = seen_at WHERE last_posted_at IS NULL")
        except sqlite3.OperationalError:
            pass  # coluna já existe
        self._conn.commit()

    def _hash(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()

    def is_new(self, deal: Deal) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM seen_deals WHERE url_hash = ?",
            (self._hash(deal.url),),
        )
        return cur.fetchone() is None

    def can_repost(self, deal: Deal) -> bool:
        """Retorna True se a promo quente pode ser re-postada (intervalo decorrido)."""
        if deal.discount_pct is None or deal.discount_pct < MIN_HOT_DISCOUNT_PCT:
            return False
        cur = self._conn.execute(
            "SELECT last_posted_at FROM seen_deals WHERE url_hash = ?",
            (self._hash(deal.url),),
        )
        row = cur.fetchone()
        if row is None:
            return False
        last_posted = datetime.fromisoformat(row[0])
        return datetime.now(UTC) - last_posted >= timedelta(hours=REPOST_INTERVAL_HOURS)

    def mark_seen(self, deal: Deal) -> None:
        now = datetime.now(UTC).isoformat()
        # primeira vez: insere seen_at e last_posted_at
        # re-post: preserva seen_at original, atualiza last_posted_at
        self._conn.execute(
            """
            INSERT INTO seen_deals (url_hash, seen_at, last_posted_at) VALUES (?, ?, ?)
            ON CONFLICT(url_hash) DO UPDATE SET last_posted_at = excluded.last_posted_at
            """,
            (self._hash(deal.url), now, now),
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
