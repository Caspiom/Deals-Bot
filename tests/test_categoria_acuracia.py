"""Trava de regressão sobre o conjunto de referência rotulado à mão.

Cobertura (quanto sai de 'geral') não mede se o item foi para a categoria
certa — dá para "melhorar" empurrando produto para o balde errado. Este teste
mede acurácia contra rótulos humanos.

Para o relatório detalhado com os erros:
    uv run python scripts/avaliar_categorias.py
"""

from pathlib import Path

import pytest

from src.models import Deal
from src.services.category_classifier import classify

FIXTURE = Path(__file__).parent / "fixtures/categorias_referencia.tsv"

# Piso, não meta. Subir junto com as melhorias; nunca baixar para "passar".
ACURACIA_MINIMA = 0.70


def carregar() -> list[tuple[str, str]]:
    linhas = []
    for linha in FIXTURE.read_text(encoding="utf-8").splitlines():
        if not linha.strip() or linha.startswith("#"):
            continue
        esperado, _loja, titulo = linha.split("\t")
        linhas.append((esperado, titulo))
    return linhas


REFERENCIA = carregar()


def test_conjunto_de_referencia_tem_massa_suficiente():
    """Amostra pequena demais faz a métrica oscilar por ruído."""
    assert len(REFERENCIA) >= 100


def test_acuracia_nao_regride():
    acertos = sum(
        classify(Deal(title=titulo, url="x", price=1.0)) == esperado
        for esperado, titulo in REFERENCIA
    )
    acuracia = acertos / len(REFERENCIA)
    assert acuracia >= ACURACIA_MINIMA, (
        f"acurácia caiu para {acuracia:.1%} (piso {ACURACIA_MINIMA:.0%}). "
        f"Rode: uv run python scripts/avaliar_categorias.py"
    )


@pytest.mark.parametrize(
    "titulo,esperado",
    [
        # Casos que já falharam de verdade — ficam explícitos para não voltarem.
        ("Sérum Capilar Força e Nutrição Pantene", "cabelo"),
        ("Suporte magnético para carro, suporte universal", "eletronico_acessorio"),
        ("Smartphone Samsung Galaxy A36 5g 128gb", "smartphone"),
        ("Processador AMD Ryzen 7 9800X3D, AM5", "hardware_pc"),
        ("Pulseira para Apple Watch Series 10", "acessorio_smartwatch"),
        ("Mochila de Viagem para Embarque Easyjet", "bolsa_mochila"),
    ],
)
def test_casos_criticos(titulo, esperado):
    assert classify(Deal(title=titulo, url="x", price=1.0)) == esperado
