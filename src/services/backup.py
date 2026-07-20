"""Backup do banco.

O SQLite guarda o histórico de preços — dezenas de milhares de observações que
sustentam o badge de "menor preço em 30 dias" e que não se recompram: são
coletadas ao longo do tempo, não obtidas sob demanda.

VACUUM INTO é a primitiva certa aqui: produz uma cópia consistente e compacta
de um banco em uso, sem parar o bot. Copiar o arquivo à mão pode capturar um
estado intermediário entre o .db e o WAL.
"""

import sqlite3
from datetime import datetime, UTC
from pathlib import Path

from loguru import logger

from src.config.settings import BACKUP_DIR, BACKUP_KEEP, DATABASE_PATH

_PREFIXO = "deals-"
_SUFIXO = ".db"


def _rotacionar(destino: Path, manter: int) -> int:
    """Remove os backups mais antigos. O nome tem timestamp ISO, então a ordem
    alfabética é a cronológica."""
    arquivos = sorted(destino.glob(f"{_PREFIXO}*{_SUFIXO}"))
    excedentes = arquivos[:-manter] if manter > 0 else []
    for arquivo in excedentes:
        arquivo.unlink()
    return len(excedentes)


def fazer_backup(
    db_path: Path | None = None,
    destino: Path | None = None,
    manter: int = 0,
) -> Path:
    """Grava uma cópia consistente e retorna o caminho gerado."""
    origem = db_path or DATABASE_PATH
    pasta = destino or BACKUP_DIR
    pasta.mkdir(parents=True, exist_ok=True)

    carimbo = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    alvo = pasta / f"{_PREFIXO}{carimbo}{_SUFIXO}"

    conn = sqlite3.connect(origem)
    try:
        # O parâmetro de VACUUM INTO não aceita bind — o caminho é montado aqui,
        # e vem de configuração, não de entrada do usuário.
        conn.execute(f"VACUUM INTO '{alvo}'")
    finally:
        conn.close()

    removidos = _rotacionar(pasta, manter or BACKUP_KEEP)
    logger.info(
        "Backup: {} ({:.1f} MB){}",
        alvo.name,
        alvo.stat().st_size / 1_048_576,
        f" — {removidos} antigo(s) removido(s)" if removidos else "",
    )
    return alvo
