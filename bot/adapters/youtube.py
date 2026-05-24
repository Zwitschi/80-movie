"""YouTube syndication adapter and payload normalization helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from ..models import SyndicationFetchResult, SyndicationItem


class YouTubeSyndicationAdapter:
    """Normalize YouTube API payloads behind bot-owned syndication contract."""

    source_key = "youtube"

    def __init__(
        self,
        *,
        payload_loader: Callable[[], Mapping[str, Any]],
    ) -> None:
        self._payload_loader = payload_loader

    def fetch_since(self, *, checkpoint: str | None = None) -> SyndicationFetchResult:
        payload = self._payload_loader()
        return self.normalize_payload(payload, checkpoint=checkpoint)

    def normalize_payload(
        self,
        payload: Mapping[str, Any],
        *,
        checkpoint: str | None = None,
    ) -> SyndicationFetchResult:
        raw_items = payload.get("items")
        if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
            raise ValueError("YouTube payload must include an items list")

        normalized_items: list[SyndicationItem] = []
        next_checkpoint = checkpoint

        for raw_item in raw_items:
            normalized_item = _normalize_youtube_item(raw_item)

            if next_checkpoint == checkpoint:
                next_checkpoint = normalized_item.external_id

            if checkpoint and normalized_item.external_id == checkpoint:
                break

            normalized_items.append(normalized_item)

        normalized_items.reverse()
        return SyndicationFetchResult(
            items=tuple(normalized_items),
            next_checkpoint=next_checkpoint,
        )


def _normalize_youtube_item(raw_item: Any) -> SyndicationItem:
    if not isinstance(raw_item, Mapping):
        raise ValueError("YouTube payload items must be objects")

    snippet = raw_item.get("snippet")
    if not isinstance(snippet, Mapping):
        raise ValueError("YouTube payload item must include snippet")

    video_id = _resolve_video_id(raw_item, snippet)
    title = str(snippet.get("title", "")).strip()
    if not title:
        raise ValueError(f"YouTube payload item '{video_id}' is missing title")

    published_raw = str(snippet.get("publishedAt", "")).strip()
    if not published_raw:
        raise ValueError(f"YouTube payload item '{video_id}' is missing publishedAt")

    return SyndicationItem(
        source_key="youtube",
        external_id=video_id,
        title=title,
        canonical_url=f"https://www.youtube.com/watch?v={video_id}",
        published_at=_parse_published_at(published_raw),
        summary=_optional_text(snippet.get("description")),
        thumbnail_url=_resolve_thumbnail_url(snippet.get("thumbnails")),
    )


def _resolve_video_id(raw_item: Mapping[str, Any], snippet: Mapping[str, Any]) -> str:
    candidates = [
        raw_item.get("contentDetails"),
        raw_item.get("id"),
        snippet.get("resourceId"),
    ]
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        video_id = str(candidate.get("videoId", "")).strip()
        if video_id:
            return video_id

    raise ValueError("YouTube payload item is missing videoId")


def _parse_published_at(raw_value: str) -> datetime:
    normalized_value = raw_value.replace("Z", "+00:00")
    try:
        parsed_value = datetime.fromisoformat(normalized_value)
    except ValueError as exc:
        raise ValueError(f"Invalid YouTube publishedAt value: {raw_value}") from exc

    if parsed_value.tzinfo is None:
        return parsed_value.replace(tzinfo=timezone.utc)
    return parsed_value.astimezone(timezone.utc)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized_value = str(value).strip()
    return normalized_value or None


def _resolve_thumbnail_url(raw_thumbnails: Any) -> str | None:
    if not isinstance(raw_thumbnails, Mapping):
        return None

    for key in ("maxres", "standard", "high", "medium", "default"):
        thumbnail = raw_thumbnails.get(key)
        if not isinstance(thumbnail, Mapping):
            continue
        url = str(thumbnail.get("url", "")).strip()
        if url:
            return url

    return None