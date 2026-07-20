import sqlite3

import pytest

from src.services.backup import _rotacionar, fazer_backup


@pytest.fixture
def banco(tmp_path):
    caminho = tmp_path / "origem.db"
    conn = sqlite3.connect(caminho)
    conn.execute("CREATE TABLE precos (id INTEGER PRIMARY KEY, valor REAL)")
    conn.executemany("INSERT INTO precos (valor) VALUES (?)", [(i * 1.5,) for i in range(500)])
    conn.commit()
    conn.close()
    return caminho


def test_backup_preserva_os_dados(banco, tmp_path):
    destino = fazer_backup(banco, tmp_path / "backups")
    conn = sqlite3.connect(destino)
    assert conn.execute("SELECT COUNT(*) FROM precos").fetchone()[0] == 500
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    conn.close()


def test_backup_nao_altera_a_origem(banco, tmp_path):
    fazer_backup(banco, tmp_path / "backups")
    conn = sqlite3.connect(banco)
    assert conn.execute("SELECT COUNT(*) FROM precos").fetchone()[0] == 500
    conn.close()


def test_backup_funciona_com_banco_em_uso(banco, tmp_path):
    """VACUUM INTO precisa rodar sem parar o bot — a conexão fica aberta."""
    aberta = sqlite3.connect(banco)
    aberta.execute("INSERT INTO precos (valor) VALUES (99.9)")
    aberta.commit()
    try:
        destino = fazer_backup(banco, tmp_path / "backups")
    finally:
        aberta.close()

    conn = sqlite3.connect(destino)
    assert conn.execute("SELECT COUNT(*) FROM precos").fetchone()[0] == 501
    conn.close()


def test_nomes_sao_unicos_e_ordenaveis(banco, tmp_path):
    pasta = tmp_path / "backups"
    primeiro = fazer_backup(banco, pasta)
    assert primeiro.name.startswith("deals-") and primeiro.name.endswith(".db")


def test_rotacao_mantem_os_mais_recentes(tmp_path):
    pasta = tmp_path / "backups"
    pasta.mkdir()
    # nome com timestamp: ordem alfabética == cronológica
    for carimbo in ("20260101T000000Z", "20260102T000000Z", "20260103T000000Z"):
        (pasta / f"deals-{carimbo}.db").write_bytes(b"x")

    removidos = _rotacionar(pasta, manter=2)
    restantes = sorted(p.name for p in pasta.glob("deals-*.db"))
    assert removidos == 1
    assert restantes == ["deals-20260102T000000Z.db", "deals-20260103T000000Z.db"]


def test_rotacao_ignora_arquivos_de_fora(tmp_path):
    """Não pode apagar nada que não seja backup nosso, mesmo rotacionando."""
    pasta = tmp_path / "backups"
    pasta.mkdir()
    (pasta / "deals-20260101T000000Z.db").write_bytes(b"x")
    (pasta / "deals-20260102T000000Z.db").write_bytes(b"x")
    (pasta / "importante.db").write_bytes(b"x")
    (pasta / "notas.txt").write_text("nao apagar")

    removidos = _rotacionar(pasta, manter=1)

    assert removidos == 1  # rotação de fato aconteceu
    assert not (pasta / "deals-20260101T000000Z.db").exists()
    assert (pasta / "importante.db").exists()
    assert (pasta / "notas.txt").exists()


def test_rotacao_zero_nao_apaga_nada(tmp_path):
    """manter=0 delega ao padrão em fazer_backup; aqui não pode apagar tudo."""
    pasta = tmp_path / "backups"
    pasta.mkdir()
    (pasta / "deals-20260101T000000Z.db").write_bytes(b"x")

    assert _rotacionar(pasta, manter=0) == 0
    assert (pasta / "deals-20260101T000000Z.db").exists()
