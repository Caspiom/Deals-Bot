import sqlite3
from datetime import datetime, UTC
from pathlib import Path

from src.config.settings import DATABASE_PATH


class GuildConfigStore:
    def __init__(self, db_path: Path | None = None) -> None:
        path = db_path or DATABASE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._create_table()

    def _create_table(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS discord_guild_channels (
                guild_id   TEXT PRIMARY KEY,
                channel_id TEXT NOT NULL,
                set_at     TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def set_channel(self, guild_id: int, channel_id: int) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO discord_guild_channels (guild_id, channel_id, set_at)
            VALUES (?, ?, ?)
            """,
            (str(guild_id), str(channel_id), datetime.now(UTC).isoformat()),
        )
        self._conn.commit()

    def get_channel(self, guild_id: int) -> int | None:
        cur = self._conn.execute(
            "SELECT channel_id FROM discord_guild_channels WHERE guild_id = ?",
            (str(guild_id),),
        )
        row = cur.fetchone()
        return int(row[0]) if row else None

    def remove_channel(self, guild_id: int) -> None:
        self._conn.execute(
            "DELETE FROM discord_guild_channels WHERE guild_id = ?",
            (str(guild_id),),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
