import hashlib
import sqlite3
from datetime import datetime, timedelta, UTC
from pathlib import Path

from loguru import logger

from src.config.settings import DATABASE_PATH, DEALS_ACTIVE_MINUTES
from src.models import Deal
from src.services.category_classifier import classify, group_of

_SORTS = {
    "discount": "discount_pct DESC, last_seen_at DESC",
    "price_asc": "price ASC",
    "price_desc": "price DESC",
    "recent": "first_seen_at DESC",
}


def deal_id(deal: Deal) -> str:
    return hashlib.sha256(deal.key().encode()).hexdigest()[:16]


class DealCatalog:
    """Catálogo dos produtos atualmente em promoção, servido pela API.

    Um produto fica "ativo" enquanto os scrapers continuam encontrando ele em
    oferta. Quando sai de promoção ele deixa de aparecer nas coletas e expira
    sozinho após DEALS_ACTIVE_MINUTES — não existe passo explícito de remoção.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        path = db_path or DATABASE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS catalog_deals (
                id                TEXT PRIMARY KEY,
                title             TEXT NOT NULL,
                raw_title         TEXT NOT NULL DEFAULT '',
                url               TEXT NOT NULL,
                affiliate_url     TEXT NOT NULL DEFAULT '',
                price             REAL NOT NULL,
                old_price         REAL,
                discount_pct      INTEGER,
                image_url         TEXT,
                store             TEXT NOT NULL DEFAULT '',
                source            TEXT NOT NULL DEFAULT '',
                category          TEXT NOT NULL DEFAULT '',
                category_group    TEXT NOT NULL DEFAULT '',
                installments      INTEGER,
                installment_value REAL,
                coupon_code       TEXT,
                tax_note          TEXT,
                first_seen_at     TEXT NOT NULL,
                last_seen_at      TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cd_last_seen ON catalog_deals(last_seen_at);
            CREATE INDEX IF NOT EXISTS idx_cd_store     ON catalog_deals(store);
            CREATE INDEX IF NOT EXISTS idx_cd_category  ON catalog_deals(category);
        """)
        # A migração precisa vir antes do índice: em banco antigo a coluna ainda
        # não existe e o CREATE INDEX falharia.
        self._migrate_coluna("raw_title", "TEXT NOT NULL DEFAULT ''")
        self._migrate_category_group()
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cd_group ON catalog_deals(category_group)"
        )
        self._conn.commit()

    def _migrate_coluna(self, nome: str, tipo: str) -> None:
        """ALTER TABLE idempotente para bancos criados antes da coluna existir."""
        try:
            self._conn.execute(f"ALTER TABLE catalog_deals ADD COLUMN {nome} {tipo}")
        except sqlite3.OperationalError:
            pass  # coluna já existe

    def _migrate_category_group(self) -> None:
        """Adiciona category_group em bancos criados antes da coluna existir.

        Sem o backfill, as linhas antigas ficariam com grupo vazio até o produto
        ser recoletado — e sumiriam do filtro do site nesse meio-tempo.
        """
        try:
            self._conn.execute(
                "ALTER TABLE catalog_deals ADD COLUMN category_group TEXT NOT NULL DEFAULT ''"
            )
        except sqlite3.OperationalError:
            return  # coluna já existe

        categorias = [
            row[0]
            for row in self._conn.execute(
                "SELECT DISTINCT category FROM catalog_deals WHERE category != ''"
            )
        ]
        self._conn.executemany(
            "UPDATE catalog_deals SET category_group = ? WHERE category = ?",
            [(group_of(c), c) for c in categorias],
        )
        logger.info("Catálogo: category_group preenchido para {} categoria(s).", len(categorias))

    def upsert_many(self, deals: list[Deal]) -> None:
        """Registra os deals do ciclo. Preserva first_seen_at de quem já existia."""
        now = datetime.now(UTC).isoformat()
        rows = [
            (
                deal_id(d), d.title, d.raw_title, d.url, d.affiliate_url, d.price, d.old_price,
                d.discount_pct, d.image_url, d.store, d.source, categoria, group_of(categoria),
                d.installments, d.installment_value, d.coupon_code, d.tax_note,
                now, now,
            )
            for d, categoria in ((d, classify(d)) for d in deals)
        ]
        if not rows:
            return
        self._conn.executemany(
            """
            INSERT INTO catalog_deals (
                id, title, raw_title, url, affiliate_url, price, old_price,
                discount_pct, image_url, store, source, category, category_group,
                installments, installment_value, coupon_code, tax_note,
                first_seen_at, last_seen_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            -- Tudo que é derivado do deal coletado precisa ser reescrito: a
            -- categoria é função do título, e congelá-la enquanto o título muda
            -- deixa o produto preso na classificação do primeiro ciclo.
            -- Só first_seen_at é preservado.
            ON CONFLICT(id) DO UPDATE SET
                title             = excluded.title,
                raw_title         = excluded.raw_title,
                url               = excluded.url,
                affiliate_url     = excluded.affiliate_url,
                price             = excluded.price,
                old_price         = excluded.old_price,
                discount_pct      = excluded.discount_pct,
                image_url         = excluded.image_url,
                store             = excluded.store,
                source            = excluded.source,
                category          = excluded.category,
                category_group    = excluded.category_group,
                installments      = excluded.installments,
                installment_value = excluded.installment_value,
                coupon_code       = excluded.coupon_code,
                tax_note          = excluded.tax_note,
                last_seen_at      = excluded.last_seen_at
            """,
            rows,
        )
        self._conn.commit()
        logger.info("Catálogo: {} produto(s) atualizado(s).", len(rows))

    def _active_cutoff(self) -> str:
        return (datetime.now(UTC) - timedelta(minutes=DEALS_ACTIVE_MINUTES)).isoformat()

    def search(
        self,
        q: str = "",
        store: str = "",
        category: str = "",
        group: str = "",
        min_discount: int = 0,
        max_price: float | None = None,
        sort: str = "discount",
        limit: int = 24,
        offset: int = 0,
    ) -> dict:
        where = ["last_seen_at >= ?"]
        params: list = [self._active_cutoff()]

        if q:
            # ponytail: LIKE cobre bem alguns milhares de linhas; migrar para FTS5
            # se a busca ficar lenta ou precisar de ranking por relevância.
            where.append("title LIKE ?")
            params.append(f"%{q}%")
        if store:
            where.append("store = ?")
            params.append(store)
        if category:
            where.append("category = ?")
            params.append(category)
        if group:
            where.append("category_group = ?")
            params.append(group)
        if min_discount:
            where.append("discount_pct >= ?")
            params.append(min_discount)
        if max_price is not None:
            where.append("price <= ?")
            params.append(max_price)

        clause = " AND ".join(where)
        total = self._conn.execute(
            f"SELECT COUNT(*) FROM catalog_deals WHERE {clause}", params
        ).fetchone()[0]

        rows = self._conn.execute(
            f"SELECT * FROM catalog_deals WHERE {clause} "
            f"ORDER BY {_SORTS.get(sort, _SORTS['discount'])} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [dict(r) for r in rows],
        }

    def get(self, id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM catalog_deals WHERE id = ? AND last_seen_at >= ?",
            (id, self._active_cutoff()),
        ).fetchone()
        return dict(row) if row else None

    def facets(self) -> dict:
        """Lojas e categorias com contagem — alimenta os filtros do frontend."""
        cutoff = self._active_cutoff()

        def counts(column: str) -> list[dict]:
            rows = self._conn.execute(
                f"SELECT {column} AS value, COUNT(*) AS count FROM catalog_deals "
                f"WHERE last_seen_at >= ? AND {column} != '' "
                f"GROUP BY {column} ORDER BY count DESC",
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]

        return {
            "stores": counts("store"),
            "categories": counts("category"),
            "groups": counts("category_group"),
        }

    def purge_expired(self) -> int:
        """Remove definitivamente o que saiu de promoção há bastante tempo."""
        cutoff = (datetime.now(UTC) - timedelta(minutes=DEALS_ACTIVE_MINUTES * 24)).isoformat()
        cur = self._conn.execute("DELETE FROM catalog_deals WHERE last_seen_at < ?", (cutoff,))
        self._conn.commit()
        return cur.rowcount

    def close(self) -> None:
        self._conn.close()
