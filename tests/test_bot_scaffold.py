import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bot.omo_bot import config as bot_config
from bot.omo_bot.config import BotConfig, ConfigError
from bot.omo_bot.main import build_runtime, run
from bot.omo_bot.models import SyndicationSourceState
from bot.omo_bot.repositories import (
    InMemoryBotAuditLogRepository,
    InMemoryBotConfigRepository,
    InMemorySyndicationSourceRepository,
    PostgresSyndicationSourceRepository,
)
from bot.omo_bot.runtime.client import BotRuntime
from bot.omo_bot.services import BotAuditService, SyndicationPlanningService


class FakeSyndicationCursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split())

        if "SELECT to_regclass('public.bot_syndication_source')" in normalized_query:
            self.result = {
                "source_table": "bot_syndication_source" if self.connection.tables_exist else None,
                "checkpoint_table": "bot_syndication_checkpoint" if self.connection.tables_exist else None,
            }
            return

        if "FROM bot_syndication_source AS s" in normalized_query:
            assert params is not None
            source_key = params[0]
            source_row = self.connection.sources.get(source_key)
            if source_row is None:
                self.result = None
                return

            checkpoint_row = self.connection.checkpoints.get(source_key, {})
            self.result = {
                "source_key": source_key,
                "is_enabled": source_row["is_enabled"],
                "checkpoint": checkpoint_row.get("checkpoint"),
                "last_polled_at": checkpoint_row.get("last_polled_at"),
                "last_succeeded_at": checkpoint_row.get("last_succeeded_at"),
                "last_failed_at": checkpoint_row.get("last_failed_at"),
            }
            return

        if normalized_query.startswith("INSERT INTO bot_syndication_source"):
            assert params is not None
            source_key, is_enabled = params
            self.connection.sources[source_key] = {"is_enabled": is_enabled}
            return

        if normalized_query.startswith("INSERT INTO bot_syndication_checkpoint"):
            assert params is not None
            source_key, checkpoint, last_polled_at, last_succeeded_at, last_failed_at = params
            self.connection.checkpoints[source_key] = {
                "checkpoint": checkpoint,
                "last_polled_at": last_polled_at,
                "last_succeeded_at": last_succeeded_at,
                "last_failed_at": last_failed_at,
            }
            return

        raise AssertionError(f"Unexpected query: {normalized_query}")

    def fetchone(self):
        return self.result

    def close(self):
        pass


class FakeSyndicationConnection:
    def __init__(self, *, tables_exist=True):
        self.tables_exist = tables_exist
        self.sources = {}
        self.checkpoints = {}
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0

    def cursor(self, cursor_factory=None):
        return FakeSyndicationCursor(self)

    def commit(self):
        self.commit_calls += 1

    def rollback(self):
        self.rollback_calls += 1

    def close(self):
        self.close_calls += 1


def test_bot_config_from_env_parses_contract():
    config = BotConfig.from_env(
        {
            "OMO_DISCORD_TOKEN": "token-value",
            "OMO_DISCORD_GUILD_ID": "987654321",
            "OMO_DISCORD_CHANNEL_MAP": "queue:100,announcements:200",
            "DATABASE_URL": "postgresql://user:pass@localhost/omo",
            "OMO_SYNDICATION_SOURCES": "youtube",
            "OMO_SYNDICATION_POLL_SECONDS": "120",
            "OMO_LOG_LEVEL": "debug",
        }
    )

    assert config.discord_token == "token-value"
    assert config.guild_id == 987654321
    assert config.channel_map == {"queue": 100, "announcements": 200}
    assert config.database_url == "postgresql://user:pass@localhost/omo"
    assert config.syndication_sources == ("youtube",)
    assert config.syndication_poll_seconds == 120
    assert config.log_level == "DEBUG"


def test_bot_config_rejects_unsupported_syndication_sources():
    with pytest.raises(ConfigError, match="unsupported source"):
        BotConfig.from_env(
            {
                "OMO_DISCORD_TOKEN": "token-value",
                "OMO_SYNDICATION_SOURCES": "youtube,instagram",
            }
        )


def test_bot_config_requires_discord_token():
    with pytest.raises(ConfigError):
        BotConfig.from_env({})


def test_bot_config_reads_runtime_settings_from_website_env_file(
    monkeypatch, tmp_path: Path
):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OMO_DISCORD_TOKEN=file-token",
                "OMO_DISCORD_GUILD_ID=987654321",
                "OMO_DISCORD_CHANNEL_MAP=queue:100,announcements:200",
                "OMO_DATABASE_URL=postgresql://user:pass@localhost/omo",
                "OMO_SYNDICATION_SOURCES=youtube",
                "OMO_SYNDICATION_POLL_SECONDS=120",
                "OMO_LOG_LEVEL=debug",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(bot_config, "BOT_ENV_PATHS", (env_file,))
    for name in (
        "OMO_DISCORD_TOKEN",
        "OMO_DISCORD_GUILD_ID",
        "OMO_DISCORD_CHANNEL_MAP",
        "OMO_DATABASE_URL",
        "OMO_SYNDICATION_SOURCES",
        "OMO_SYNDICATION_POLL_SECONDS",
        "OMO_LOG_LEVEL",
    ):
        monkeypatch.delenv(name, raising=False)

    config = BotConfig.from_env()

    assert config.discord_token == "file-token"
    assert config.guild_id == 987654321
    assert config.channel_map == {"queue": 100, "announcements": 200}
    assert config.database_url == "postgresql://user:pass@localhost/omo"
    assert config.syndication_sources == ("youtube",)
    assert config.syndication_poll_seconds == 120
    assert config.log_level == "DEBUG"


def test_bot_run_starts_and_stops_runtime():
    config = BotConfig.from_env(
        {
            "OMO_DISCORD_TOKEN": "token-value",
            "OMO_DISCORD_CHANNEL_MAP": "queue:100",
        }
    )
    runtime = build_runtime(config, __import__(
        "logging").getLogger("test-bot"))
    shutdown_event = asyncio.Event()
    shutdown_event.set()

    asyncio.run(run(config=config, runtime=runtime,
                shutdown_event=shutdown_event))

    snapshot = runtime.health_snapshot()
    assert snapshot["state"] == "stopped"
    assert snapshot["configured_channels"] == ["queue"]
    assert snapshot["syndication_repository_backend"] == "InMemorySyndicationSourceRepository"
    assert snapshot["last_started_at"] is not None
    assert snapshot["polling_task_state"] == "stopped"


def test_build_runtime_uses_in_memory_repository_without_database_url():
    config = BotConfig.from_env(
        {
            "OMO_DISCORD_TOKEN": "token-value",
            "OMO_SYNDICATION_SOURCES": "youtube",
        }
    )

    runtime = build_runtime(config, __import__(
        "logging").getLogger("test-bot"))

    assert isinstance(runtime.syndication_repository,
                      InMemorySyndicationSourceRepository)


def test_build_runtime_uses_postgres_repository_with_database_url():
    config = BotConfig.from_env(
        {
            "OMO_DISCORD_TOKEN": "token-value",
            "DATABASE_URL": "postgresql://user:pass@localhost/omo",
            "OMO_SYNDICATION_SOURCES": "youtube",
        }
    )

    runtime = build_runtime(config, __import__(
        "logging").getLogger("test-bot"))

    assert isinstance(runtime.syndication_repository,
                      PostgresSyndicationSourceRepository)


def test_build_runtime_uses_discord_delivery_sink_when_channels_configured():
    config = BotConfig.from_env(
        {
            "OMO_DISCORD_TOKEN": "token-value",
            "OMO_DISCORD_CHANNEL_MAP": "announcements:200",
            "OMO_SYNDICATION_SOURCES": "youtube",
        }
    )

    runtime = build_runtime(config, __import__(
        "logging").getLogger("test-bot"))

    assert runtime.health_snapshot(
    )["syndication_delivery_backend"] == "DiscordApiSyndicationDeliverySink"


def test_build_runtime_uses_repository_managed_config(monkeypatch):
    config = BotConfig.from_env(
        {
            "OMO_DISCORD_TOKEN": "token-value",
            "OMO_DISCORD_GUILD_ID": "111",
            "OMO_DISCORD_CHANNEL_MAP": "announcements:200",
            "DATABASE_URL": "postgresql://user:pass@localhost/omo",
            "OMO_SYNDICATION_SOURCES": "youtube",
        }
    )
    monkeypatch.setattr(
        "bot.omo_bot.main.build_postgres_bot_config_repository",
        lambda database_url: InMemoryBotConfigRepository(
            guild_id=222,
            channel_map={"queue": 300},
            role_map={"moderator": 400},
        ),
    )

    runtime = build_runtime(config, __import__(
        "logging").getLogger("test-bot"))

    snapshot = runtime.health_snapshot()
    assert snapshot["guild_id"] == 222
    assert snapshot["configured_channels"] == ["queue"]
    assert snapshot["configured_roles"] == ["moderator"]


def test_bot_audit_service_records_append_only_entries():
    repository = InMemoryBotAuditLogRepository()
    service = BotAuditService(repository)

    entry = service.record(
        actor_user_id="123456",
        actor_session_id="session-1",
        action_key="syndication.source.disabled",
        target_type="syndication_source",
        target_key="youtube",
        request_id="request-1",
        before_state={"enabled": True},
        after_state={"enabled": False},
    )

    assert entry.action_key == "syndication.source.disabled"
    assert len(repository.entries) == 1
    assert repository.entries[0].target_key == "youtube"


def test_bot_runtime_polling_loop_updates_health_snapshot():
    class RecordingPollingJob:
        def __init__(self) -> None:
            self.run_calls = 0

        def run(self, *, now=None):
            self.run_calls += 1

            class Result:
                polled_sources = ("youtube",)
                delivered_items = 1
                failed_sources = ()

            return Result()

    config = BotConfig.from_env(
        {
            "OMO_DISCORD_TOKEN": "token-value",
            "OMO_SYNDICATION_SOURCES": "youtube",
            "OMO_SYNDICATION_POLL_SECONDS": "60",
        }
    )
    runtime = BotRuntime(
        config=config,
        logger=__import__("logging").getLogger("test-bot"),
        syndication_repository=InMemorySyndicationSourceRepository(),
        syndication_planning_service=SyndicationPlanningService(
            config=config,
            repository=InMemorySyndicationSourceRepository(),
        ),
        syndication_polling_job=RecordingPollingJob(),
        syndication_delivery_sink=object(),
    )

    async def scenario():
        await runtime.start()
        await asyncio.sleep(0)
        await runtime.close()

    asyncio.run(scenario())

    snapshot = runtime.health_snapshot()
    assert snapshot["last_poll_started_at"] is not None
    assert snapshot["last_poll_completed_at"] is not None
    assert snapshot["last_poll_delivered_items"] == 1
    assert snapshot["last_poll_sources"] == ["youtube"]
    assert snapshot["last_poll_error"] is None


def test_syndication_planning_service_creates_due_state_for_configured_source():
    config = BotConfig.from_env(
        {
            "OMO_DISCORD_TOKEN": "token-value",
            "OMO_SYNDICATION_SOURCES": "youtube",
            "OMO_SYNDICATION_POLL_SECONDS": "300",
        }
    )
    repository = InMemorySyndicationSourceRepository()
    service = SyndicationPlanningService(config=config, repository=repository)

    due_sources = service.list_due_sources(
        now=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc)
    )

    assert [source.source_key for source in due_sources] == ["youtube"]
    assert repository.get_by_source_key("youtube") is not None


def test_syndication_planning_service_skips_recently_polled_source():
    config = BotConfig.from_env(
        {
            "OMO_DISCORD_TOKEN": "token-value",
            "OMO_SYNDICATION_SOURCES": "youtube",
            "OMO_SYNDICATION_POLL_SECONDS": "300",
        }
    )
    now = datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc)
    repository = InMemorySyndicationSourceRepository(
        [
            SyndicationSourceState(
                source_key="youtube",
                last_polled_at=now - timedelta(seconds=120),
            )
        ]
    )
    service = SyndicationPlanningService(config=config, repository=repository)

    due_sources = service.list_due_sources(now=now)

    assert due_sources == []


def test_syndication_planning_service_includes_overdue_source():
    config = BotConfig.from_env(
        {
            "OMO_DISCORD_TOKEN": "token-value",
            "OMO_SYNDICATION_SOURCES": "youtube",
            "OMO_SYNDICATION_POLL_SECONDS": "300",
        }
    )
    now = datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc)
    repository = InMemorySyndicationSourceRepository(
        [
            SyndicationSourceState(
                source_key="youtube",
                last_polled_at=now - timedelta(seconds=301),
            )
        ]
    )
    service = SyndicationPlanningService(config=config, repository=repository)

    due_sources = service.list_due_sources(now=now)

    assert [source.source_key for source in due_sources] == ["youtube"]


def test_postgres_syndication_source_repository_round_trips_state():
    fake_connection = FakeSyndicationConnection()
    repository = PostgresSyndicationSourceRepository(
        connection_factory=lambda: fake_connection
    )
    state = SyndicationSourceState(
        source_key="youtube",
        enabled=True,
        checkpoint="video-123",
        last_polled_at=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc),
        last_succeeded_at=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc),
    )

    saved_state = repository.save(state)
    loaded_state = repository.get_by_source_key("youtube")

    assert saved_state == state
    assert loaded_state == state
    assert fake_connection.commit_calls == 1
    assert fake_connection.rollback_calls == 0
    assert fake_connection.close_calls == 2


def test_postgres_syndication_source_repository_returns_none_when_tables_missing():
    fake_connection = FakeSyndicationConnection(tables_exist=False)
    repository = PostgresSyndicationSourceRepository(
        connection_factory=lambda: fake_connection
    )

    loaded_state = repository.get_by_source_key("youtube")

    assert loaded_state is None
