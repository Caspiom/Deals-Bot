import pytest

from src.models import Deal
from src.services.category_classifier import (
    _singularize_word,
    classify,
    normalize,
)


def _deal(title: str, raw_title: str = "") -> Deal:
    return Deal(title=title, url="https://loja.com/p", price=99.9, raw_title=raw_title)


# ── normalize ────────────────────────────────────────────────────────────────

def test_normalize_strips_accents_and_case():
    assert normalize("Memória RAM Vídeo") == "memoria ram video"


def test_normalize_collapses_whitespace():
    assert normalize("  fone   de \n ouvido ") == "fone de ouvido"


# ── singularização ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "plural,singular",
    [
        ("fones", "fone"),
        ("cabos", "cabo"),
        ("mochilas", "mochila"),
        ("ferramentas", "ferramenta"),
        ("colheres", "colher"),
        ("papeis", "papel"),      # -eis → -el
        ("cordoes", "cordao"),    # -oes → -ao (após remoção de acento)
        ("jardins", "jardim"),    # -ns  → -m
    ],
)
def test_singularize_common_plurals(plural, singular):
    assert _singularize_word(plural) == singular


@pytest.mark.parametrize("word", ["tenis", "lapis", "virus", "gas", "wireless", "fitness"])
def test_singularize_leaves_invariant_words(word):
    """Singulares terminados em -s não podem virar lixo ('tenis' → 'teni')."""
    assert _singularize_word(word) == word


# ── classify ─────────────────────────────────────────────────────────────────

def test_classify_matches_plural_form():
    """Bug original: 'fones de ouvido' não casava com o padrão no singular."""
    assert classify(_deal("Fones de Ouvido Sem Fio por Condução Óssea")) == "fone_headset"


def test_classify_matches_singular_form():
    assert classify(_deal("Fone de ouvido bluetooth")) == "fone_headset"


def test_classify_matches_without_accents():
    assert classify(_deal("Memoria RAM Husky 8GB DDR4")) == "eletronico_geral"


def test_classify_uses_raw_title_when_available():
    """Título limpo perde o termo do produto; o original ainda o tem."""
    deal = _deal("Kerokuru cabo organizador", raw_title="Fones de ouvido bluetooth TWS")
    assert classify(deal) == "fone_headset"


def test_classify_falls_back_to_geral():
    assert classify(_deal("Produto genérico sem termo reconhecível")) == "geral"


def test_specific_category_wins_over_generic():
    """Ordem importa: 'carrinho de bebê' é mais específico que 'copo'."""
    assert classify(_deal("Suportes para copos de carrinho de bebê")) == "bebe"
