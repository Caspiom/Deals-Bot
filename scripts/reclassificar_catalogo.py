#!/usr/bin/env python
"""Reclassifica todo o catálogo com o classificador atual.

O upsert só recalcula a categoria dos produtos que a coleta traz de volta —
um produto ainda dentro da janela ativa, mas ausente do ciclo, mantém a
classificação antiga. Depois de mexer no classificador, rode isto para
propagar a mudança sem esperar cada item reaparecer.

    uv run python scripts/reclassificar_catalogo.py          # aplica
    uv run python scripts/reclassificar_catalogo.py --dry    # só mostra
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.settings import DATABASE_PATH  # noqa: E402
from src.models import Deal  # noqa: E402
from src.services.catalog import DealCatalog  # noqa: E402
from src.services.category_classifier import classify, group_of  # noqa: E402


def reclassificar(dry: bool = False) -> None:
    catalog = DealCatalog(DATABASE_PATH)
    linhas = catalog._conn.execute(
        "SELECT id, title, raw_title, category, category_group FROM catalog_deals"
    ).fetchall()

    mudancas: list[tuple[str, str, str]] = []
    resumo: Counter[str] = Counter()
    for row in linhas:
        # raw_title é o mesmo sinal usado na classificação original; sem ele,
        # o título limpo é o melhor disponível.
        nova = classify(
            Deal(title=row["title"], raw_title=row["raw_title"], url="x", price=1.0)
        )
        grupo = group_of(nova)
        if nova != row["category"] or grupo != row["category_group"]:
            mudancas.append((nova, grupo, row["id"]))
            resumo[f"{row['category'] or '(vazio)'} -> {nova}"] += 1

    print(f"catálogo: {len(linhas)} itens | mudam: {len(mudancas)}\n")
    for mudanca, n in resumo.most_common(15):
        print(f"  {n:>4}x  {mudanca}")

    if dry:
        print("\n--dry: nada gravado.")
    elif mudancas:
        catalog._conn.executemany(
            "UPDATE catalog_deals SET category = ?, category_group = ? WHERE id = ?",
            mudancas,
        )
        catalog._conn.commit()
        print(f"\n{len(mudancas)} linha(s) atualizada(s).")

    catalog.close()


if __name__ == "__main__":
    reclassificar(dry="--dry" in sys.argv)
