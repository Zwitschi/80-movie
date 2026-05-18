import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from bot.omo_bot.config import BotConfig, ConfigError
from bot.omo_bot.main import run
from bot.omo_bot.models import SyndicationSourceState
from bot.omo_bot.repositories import InMemorySyndicationSourceRepository
from bot.omo_bot.runtime.client import BotRuntime
from bot.omo_bot.services import SyndicationPlanningService


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


def test_bot_run_starts_and_stops_runtime():
    config = BotConfig.from_env(
        {
            "OMO_DISCORD_TOKEN": "token-value",
            "OMO_DISCORD_CHANNEL_MAP": "queue:100",
        }
    )
    runtime = BotRuntime(config=config, logger=__import__(
        "logging").getLogger("test-bot"))
    shutdown_event = asyncio.Event()
    shutdown_event.set()

    asyncio.run(run(config=config, runtime=runtime,
                shutdown_event=shutdown_event))

    snapshot = runtime.health_snapshot()
    assert snapshot["state"] == "stopped"
    assert snapshot["configured_channels"] == ["queue"]
    assert snapshot["last_started_at"] is not None


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
