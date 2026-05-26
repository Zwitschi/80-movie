"""Delivery seam for normalized syndication items."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol
from urllib.request import Request, urlopen

from ..models import SyndicationItem

OMO_USER_AGENT = 'OpenMicOdysseyBot/1.0 (+https://www.openmicodyssey.com)'


@dataclass(frozen=True)
class SyndicationDeliveryBatch:
    """Normalized batch ready for downstream publish or queue handling."""

    source_key: str
    items: tuple[SyndicationItem, ...]


class SyndicationDeliverySink(Protocol):
    """Explicit seam between polling and downstream posting or queue work."""

    def deliver(self, batch: SyndicationDeliveryBatch) -> None:
        """Accept normalized items for later posting or queue processing."""


class DiscordApiSyndicationDeliverySink:
    """Post normalized syndication items to Discord channels via the REST API."""

    def __init__(
        self,
        *,
        bot_token: str,
        channel_map: dict[str, int],
    ) -> None:
        self._bot_token = bot_token
        self._channel_map = dict(channel_map)

    def deliver(self, batch: SyndicationDeliveryBatch) -> None:
        channel_id = self._resolve_channel_id(batch.source_key)
        for item in batch.items:
            payload = {
                "content": self._render_message(item),
                "allowed_mentions": {"parse": []},
            }
            request = Request(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bot {self._bot_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": OMO_USER_AGENT,
                },
                method="POST",
            )
            with urlopen(request, timeout=10) as response:
                response.read()

    def _resolve_channel_id(self, source_key: str) -> int:
        if source_key in self._channel_map:
            return self._channel_map[source_key]
        if "announcements" in self._channel_map:
            return self._channel_map["announcements"]
        first_channel_id = next(iter(self._channel_map.values()), None)
        if first_channel_id is None:
            raise RuntimeError(
                "Discord delivery requires at least one configured channel binding"
            )
        return first_channel_id

    @staticmethod
    def _render_message(item: SyndicationItem) -> str:
        source_label = item.source_key.replace("_", " ").title()
        lines = [f"[{source_label}] {item.title}", item.canonical_url]
        if item.summary:
            lines.append(item.summary)
        return "\n".join(lines)


class NullSyndicationDeliverySink:
    """Default delivery sink used while posting contract settles."""

    def deliver(self, batch: SyndicationDeliveryBatch) -> None:
        return None
