#!/usr/bin/env python
"""Backup manual do banco — rode antes de migração ou manutenção arriscada.

O bot já faz um backup diário sozinho; isto é para o backup sob demanda.

    uv run python scripts/backup_db.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.backup import fazer_backup  # noqa: E402

if __name__ == "__main__":
    caminho = fazer_backup()
    print(caminho)
