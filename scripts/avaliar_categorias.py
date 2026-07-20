#!/usr/bin/env python
"""Mede a ACURÁCIA da classificação de categoria contra o conjunto de referência.

Cobertura (quanto sai de 'geral') não diz se o item foi para a categoria certa —
dá para melhorar cobertura empurrando produto para o balde errado. Este script
compara contra rótulos humanos.

    uv run python scripts/avaliar_categorias.py           # resumo + erros
    uv run python scripts/avaliar_categorias.py --tudo    # inclui acertos
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import Deal  # noqa: E402
from src.services.category_classifier import classify  # noqa: E402

FIXTURE = Path(__file__).resolve().parent.parent / "tests/fixtures/categorias_referencia.tsv"


def carregar() -> list[tuple[str, str, str]]:
    linhas = []
    for linha in FIXTURE.read_text(encoding="utf-8").splitlines():
        if not linha.strip() or linha.startswith("#"):
            continue
        esperado, loja, titulo = linha.split("\t")
        linhas.append((esperado, loja, titulo))
    return linhas


def avaliar():
    dados = carregar()
    acertos = 0
    erros: list[tuple[str, str, str, str]] = []
    por_cat_total: Counter[str] = Counter()
    por_cat_acerto: Counter[str] = Counter()
    confusao: defaultdict[tuple[str, str], int] = defaultdict(int)

    for esperado, loja, titulo in dados:
        obtido = classify(Deal(title=titulo, url="x", price=1.0))
        por_cat_total[esperado] += 1
        if obtido == esperado:
            acertos += 1
            por_cat_acerto[esperado] += 1
        else:
            erros.append((esperado, obtido, loja, titulo))
            confusao[(esperado, obtido)] += 1

    total = len(dados)
    print(f"\nACURÁCIA: {acertos}/{total} = {acertos * 100 / total:.1f}%\n")

    print("por categoria esperada (recall):")
    for cat in sorted(por_cat_total, key=lambda c: -por_cat_total[c]):
        n, ok = por_cat_total[cat], por_cat_acerto[cat]
        barra = "█" * round(ok * 10 / n) + "·" * (10 - round(ok * 10 / n))
        print(f"  {cat:<24} {barra} {ok:>2}/{n:<3} {ok * 100 / n:>5.0f}%")

    if confusao:
        print("\nconfusões mais frequentes (esperado -> obtido):")
        for (esp, obt), q in sorted(confusao.items(), key=lambda x: -x[1])[:12]:
            print(f"  {q:>2}x  {esp:<24} -> {obt}")

    if erros:
        print(f"\nerros ({len(erros)}):")
        for esperado, obtido, loja, titulo in erros:
            print(f"  esperado={esperado:<22} obtido={obtido:<22} [{loja}]")
            print(f"       {titulo[:88]}")

    return acertos / total


if __name__ == "__main__":
    avaliar()
