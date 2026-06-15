import pytest
from src.services.guild_config import GuildConfigStore


@pytest.fixture
def store(tmp_path):
    s = GuildConfigStore(db_path=tmp_path / "test.db")
    yield s
    s.close()


def test_get_returns_none_when_not_configured(store):
    assert store.get_channel(guild_id=111) is None


def test_set_and_get_channel(store):
    store.set_channel(guild_id=111, channel_id=999)
    assert store.get_channel(guild_id=111) == 999


def test_set_is_idempotent(store):
    store.set_channel(guild_id=111, channel_id=999)
    store.set_channel(guild_id=111, channel_id=888)
    assert store.get_channel(guild_id=111) == 888


def test_guilds_are_independent(store):
    store.set_channel(guild_id=111, channel_id=1)
    store.set_channel(guild_id=222, channel_id=2)
    assert store.get_channel(guild_id=111) == 1
    assert store.get_channel(guild_id=222) == 2


def test_remove_channel(store):
    store.set_channel(guild_id=111, channel_id=999)
    store.remove_channel(guild_id=111)
    assert store.get_channel(guild_id=111) is None


def test_remove_nonexistent_is_safe(store):
    store.remove_channel(guild_id=999)  # não deve lançar erro
