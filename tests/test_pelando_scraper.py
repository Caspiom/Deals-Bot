import pytest
from src.scrapers.pelando_scraper import _parse_brl, _extract_pct_from_title


# ── testes das funções de parsing (sem Playwright) ──────────────────────────

def test_parse_brl_simple():
    assert _parse_brl("R$\n9,90") == 9.90

def test_parse_brl_thousands():
    assert _parse_brl("R$\n1.799,90") == 1799.90

def test_parse_brl_large():
    assert _parse_brl("R$\n3.199,00") == 3199.00

def test_parse_brl_invalid_returns_none():
    assert _parse_brl("Grátis") is None

def test_extract_pct_desconto():
    assert _extract_pct_from_title("Galaxy S24 com 40% de Desconto") == 40

def test_extract_pct_off():
    assert _extract_pct_from_title("Smart TV 4K com 55% OFF") == 55

def test_extract_pct_parenthesis():
    assert _extract_pct_from_title("(Selecionados) Amazon Prime com 83% de Desconto") == 83

def test_extract_pct_none_when_absent():
    assert _extract_pct_from_title("Fone Bluetooth Anker mais barato do ano") is None
