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
    """Padrão escrito com acento ('câmera') casa o título sem acento."""
    assert classify(_deal("Camera de acao 4K a prova d'agua")) == "eletronico_geral"


def test_classify_uses_raw_title_when_available():
    """Título limpo perde o termo do produto; o original ainda o tem."""
    deal = _deal("Kerokuru cabo organizador", raw_title="Fones de ouvido bluetooth TWS")
    assert classify(deal) == "fone_headset"


def test_classify_falls_back_to_geral():
    assert classify(_deal("Produto genérico sem termo reconhecível")) == "geral"


def test_specific_category_wins_over_generic():
    """Ordem importa: 'carrinho de bebê' é mais específico que 'copo'."""
    assert classify(_deal("Suportes para copos de carrinho de bebê")) == "bebe"


# ── categorias novas e precedência ───────────────────────────────────────────

@pytest.mark.parametrize(
    "title",
    [
        "Processador AMD Ryzen 5 5500, 3.6GHz, Cache 19MB, AM4",
        "Placa de Vídeo Galax GeForce RTX 3050 EX V2, 6GB",
        "Placa-Mãe MSI B550M Pro-VDH WiFi, AMD AM4, mATX",
        "SSD SanDisk, 480GB, M.2, Leitura 545MB/s",
        "Water Cooler MACH1 Logic, RGB, 360mm, AMD e Intel",
        "Gabinete Gamer Rise Mode Galaxy Glass M Mini, M-ATX",
        "Memória RAM Corsair Vengeance 32GB DDR5",
    ],
)
def test_hardware_pc(title):
    assert classify(_deal(title)) == "hardware_pc"


@pytest.mark.parametrize(
    "title,expected",
    [
        # Aparelho ganha do componente: celular e notebook citam RAM/SSD/Ryzen.
        ("Smartphone Infinix Smart 10 4GB RAM 256GB SSD", "smartphone"),
        ("Notebook Lenovo IdeaPad Slim 3 AMD Ryzen 5, 16GB, SSD 512GB", "notebook"),
        # 'processador' sozinho não pode capturar eletrodoméstico.
        ("Processador de alimentos Philips Walita 800W", "eletrodomestico_pequeno"),
    ],
)
def test_hardware_pc_does_not_steal_devices(title, expected):
    assert classify(_deal(title)) == expected


@pytest.mark.parametrize(
    "title",
    [
        "Mochila de Viagem para Embarque Easyjet",
        "Nova mochila de bicicleta impermeável ao ar livre",
        "Bolsa feminina transversal de couro",
    ],
)
def test_bolsa_mochila(title):
    assert classify(_deal(title)) == "bolsa_mochila"


def test_bolsa_mochila_ignores_shape_description():
    """'em formato de mochila' descreve a forma, não o produto."""
    assert classify(_deal("Almofada Protetora de Cabeça para Bebês em Formato de Mochila")) != "bolsa_mochila"


def test_bolsa_mochila_does_not_catch_charging_case():
    assert classify(_deal("AirPods 4 Apple com Estojo de Recarga USB-C")) == "fone_headset"


@pytest.mark.parametrize(
    "title",
    [
        "Pulseira para Apple Watch Series 10 46mm 42mm",
        "Pulseiras esportivas de silicone para apple watch band 45mm",
        "Caixa de relógio com 5 slots",
    ],
)
def test_acessorio_smartwatch(title):
    assert classify(_deal(title)) == "acessorio_smartwatch"


def test_smartwatch_device_is_not_accessory():
    """O relógio em si continua sendo o aparelho, não o acessório."""
    assert classify(_deal("Smartwatch Amazfit GTS 4 Mini")) == "eletronico_acessorio"


def test_wifi_alone_does_not_imply_router():
    """'Wi-Fi' é característica; capturava câmera, impressora e TV."""
    assert classify(_deal("TP-Link Tapo C500 Câmera de Segurança Wifi 1080P")) == "eletronico_geral"
