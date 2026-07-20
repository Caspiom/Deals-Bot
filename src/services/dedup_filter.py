import hashlib
import sqlite3
from datetime import datetime, timedelta, UTC
from pathlib import Path

from loguru import logger

from src.config.settings import (
    DATABASE_PATH,
    DEDUP_TTL_DAYS,
    HIGH_DISCOUNT_PCT,
    REPOST_HIGH_HOURS,
    REPOST_LOW_HOURS,
)
from src.models import Deal

_PRICE_HISTORY_DAYS = 31
_MIN_PRICE_OBSERVATIONS = 3  # número mínimo de ciclos para exibir badge "menor preço"


class DedupFilter:
    def __init__(self, db_path: Path | None = None) -> None:
        path = db_path or DATABASE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
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

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                url_hash TEXT    NOT NULL,
                price    REAL    NOT NULL,
                seen_at  TEXT    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ph_url_seen ON price_history(url_hash, seen_at)"
        )
        self._conn.commit()

    def _hash(self, url: str) -> str:
        # Remove query string e fragment para que o mesmo produto
        # não seja tratado como novo quando parâmetros de tracking mudam.
        clean = url.split("?")[0].split("#")[0].rstrip("/")
        return hashlib.sha256(clean.encode()).hexdigest()

    def is_new(self, deal: Deal) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM seen_deals WHERE url_hash = ?",
            (self._hash(deal.dedup_key or deal.url),),
        )
        return cur.fetchone() is None

    def can_repost(self, deal: Deal) -> bool:
        """Retorna True se o deal ainda está ativo e o intervalo mínimo já passou.

        >= HIGH_DISCOUNT_PCT → repost a cada REPOST_HIGH_HOURS (padrão 24h).
        Abaixo disso        → repost a cada REPOST_LOW_HOURS  (padrão 48h).
        """
        cur = self._conn.execute(
            "SELECT last_posted_at FROM seen_deals WHERE url_hash = ?",
            (self._hash(deal.dedup_key or deal.url),),
        )
        row = cur.fetchone()
        if row is None:
            return False
        interval = (
            REPOST_HIGH_HOURS
            if (deal.discount_pct or 0) >= HIGH_DISCOUNT_PCT
            else REPOST_LOW_HOURS
        )
        try:
            last_posted = datetime.fromisoformat(row[0])
        except (ValueError, TypeError):
            return False
        return datetime.now(UTC) - last_posted >= timedelta(hours=interval)

    def mark_seen(self, deal: Deal) -> None:
        now = datetime.now(UTC).isoformat()
        # primeira vez: insere seen_at e last_posted_at
        # re-post: preserva seen_at original, atualiza last_posted_at
        try:
            self._conn.execute(
                """
                INSERT INTO seen_deals (url_hash, seen_at, last_posted_at) VALUES (?, ?, ?)
                ON CONFLICT(url_hash) DO UPDATE SET last_posted_at = excluded.last_posted_at
                """,
                (self._hash(deal.dedup_key or deal.url), now, now),
            )
            self._conn.commit()
        except sqlite3.OperationalError as exc:
            logger.error("Falha ao marcar deal como visto ({}): {}", deal.title[:40], exc)
        logger.debug("Marcado como visto: {}", deal.title[:60])

    def record_prices(self, deals: list[Deal]) -> None:
        """Registra o preço de todos os deals do ciclo para histórico de 30 dias."""
        now = datetime.now(UTC).isoformat()
        seen: set[str] = set()
        rows: list[tuple[str, float, str]] = []
        for deal in deals:
            h = self._hash(deal.dedup_key or deal.url)
            if h not in seen:
                seen.add(h)
                rows.append((h, deal.price, now))
        if rows:
            self._conn.executemany(
                "INSERT INTO price_history (url_hash, price, seen_at) VALUES (?, ?, ?)",
                rows,
            )
            self._conn.commit()

    def get_min_price_30d(self, deal: Deal) -> tuple[float, int]:
        """Retorna (menor_preço, total_observações) nos últimos 30 dias para este deal."""
        cur = self._conn.execute(
            """
            SELECT MIN(price), COUNT(*) FROM price_history
            WHERE url_hash = ? AND seen_at >= datetime('now', '-30 days')
            """,
            (self._hash(deal.dedup_key or deal.url),),
        )
        row = cur.fetchone()
        min_price = row[0] if row[0] is not None else deal.price
        count = row[1] if row[1] is not None else 0
        return min_price, count

    def is_lowest_price(self, deal: Deal) -> bool:
        """True se o preço atual é o menor dos últimos 30 dias e há histórico suficiente."""
        min_price, count = self.get_min_price_30d(deal)
        return count >= _MIN_PRICE_OBSERVATIONS and deal.price <= min_price

    def _purge_expired(self) -> None:
        cutoff = (datetime.now(UTC) - timedelta(days=DEDUP_TTL_DAYS)).isoformat()
        ph_cutoff = (datetime.now(UTC) - timedelta(days=_PRICE_HISTORY_DAYS)).isoformat()
        cur = self._conn.execute("DELETE FROM seen_deals WHERE seen_at < ?", (cutoff,))
        self._conn.execute("DELETE FROM price_history WHERE seen_at < ?", (ph_cutoff,))
        self._conn.commit()
        if cur.rowcount:
            logger.info("Dedup: {} registro(s) expirado(s) removido(s).", cur.rowcount)

    def close(self) -> None:
        self._conn.close()
