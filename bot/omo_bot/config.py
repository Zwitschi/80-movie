"""Configuration parsing for the Discord bot runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


class ConfigError(ValueError):
    """Raised when required bot configuration is missing or invalid."""


SUPPORTED_SYNDICATION_SOURCES = ("youtube",)


def _parse_optional_int(raw_value: str | None, field_name: str) -> int | None:
    if raw_value in (None, ""):
        return None

    try:
        return int(raw_value)
    except ValueError as exc:
        raise ConfigError(f"{field_name} must be an integer") from exc


def _parse_channel_map(raw_value: str | None) -> dict[str, int]:
    if not raw_value:
        return {}

    channel_map: dict[str, int] = {}
    for item in raw_value.split(","):
        name, separator, raw_channel_id = item.partition(":")
        if not separator or not name.strip() or not raw_channel_id.strip():
            raise ConfigError(
                "OMO_DISCORD_CHANNEL_MAP must use name:id pairs separated by commas"
            )

        try:
            channel_map[name.strip()] = int(raw_channel_id.strip())
        except ValueError as exc:
            raise ConfigError(
                f"Channel id for '{name.strip()}' must be an integer"
            ) from exc

    return channel_map


def _parse_sources(raw_value: str | None) -> tuple[str, ...]:
    if not raw_value:
        return ()

    parsed_sources = tuple(
        source.strip().lower() for source in raw_value.split(",") if source.strip()
    )

    unsupported_sources = sorted(
        {source for source in parsed_sources if source not in SUPPORTED_SYNDICATION_SOURCES}
    )
    if unsupported_sources:
        allowed_sources = ", ".join(SUPPORTED_SYNDICATION_SOURCES)
        invalid_sources = ", ".join(unsupported_sources)
        raise ConfigError(
            f"OMO_SYNDICATION_SOURCES contains unsupported source(s): {invalid_sources}. "
            f"Supported sources: {allowed_sources}"
        )

    return parsed_sources


@dataclass(frozen=True)
class BotConfig:
    """Runtime configuration for the Discord bot."""

    discord_token: str
    guild_id: int | None
    channel_map: dict[str, int]
    database_url: str | None
    syndication_sources: tuple[str, ...]
    syndication_poll_seconds: int
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "BotConfig":
        source_env = os.environ if env is None else env

        discord_token = source_env.get(
            "OMO_DISCORD_TOKEN") or source_env.get("DISCORD_TOKEN")
        if not discord_token:
            raise ConfigError(
                "OMO_DISCORD_TOKEN is required to start the Discord bot")

        guild_id = _parse_optional_int(
            source_env.get("OMO_DISCORD_GUILD_ID"),
            "OMO_DISCORD_GUILD_ID",
        )
        channel_map = _parse_channel_map(
            source_env.get("OMO_DISCORD_CHANNEL_MAP"))
        database_url = source_env.get(
            "OMO_DATABASE_URL") or source_env.get("DATABASE_URL")
        syndication_sources = _parse_sources(
            source_env.get("OMO_SYNDICATION_SOURCES"))

        poll_raw_value = source_env.get("OMO_SYNDICATION_POLL_SECONDS", "300")
        try:
            syndication_poll_seconds = int(poll_raw_value)
        except ValueError as exc:
            raise ConfigError(
                "OMO_SYNDICATION_POLL_SECONDS must be an integer") from exc

        if syndication_poll_seconds <= 0:
            raise ConfigError(
                "OMO_SYNDICATION_POLL_SECONDS must be greater than zero")

        log_level = source_env.get("OMO_LOG_LEVEL", "INFO").upper()

        return cls(
            discord_token=discord_token,
            guild_id=guild_id,
            channel_map=channel_map,
            database_url=database_url,
            syndication_sources=syndication_sources,
            syndication_poll_seconds=syndication_poll_seconds,
            log_level=log_level,
        )
