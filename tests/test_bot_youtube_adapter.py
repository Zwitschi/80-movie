from datetime import datetime, timezone

import pytest

from bot.omo_bot.adapters import SyndicationAdapter, YouTubeSyndicationAdapter


def test_youtube_adapter_implements_syndication_contract():
    adapter: SyndicationAdapter = YouTubeSyndicationAdapter(
        payload_loader=lambda: {"items": []}
    )

    result = adapter.fetch_since()

    assert result.items == ()
    assert result.next_checkpoint is None


def test_youtube_adapter_normalizes_playlist_items_without_provider_shape_leakage():
    adapter = YouTubeSyndicationAdapter(
        payload_loader=lambda: {
            "items": [
                {
                    "snippet": {
                        "title": "Fresh trailer drop",
                        "description": "Road update from production.",
                        "publishedAt": "2026-05-18T10:15:00Z",
                        "resourceId": {"videoId": "video-123"},
                        "thumbnails": {
                            "default": {"url": "https://img.youtube.com/default.jpg"},
                            "high": {"url": "https://img.youtube.com/high.jpg"},
                        },
                    }
                }
            ]
        }
    )

    result = adapter.fetch_since()

    assert result.next_checkpoint == "video-123"
    assert len(result.items) == 1

    item = result.items[0]
    assert item.source_key == "youtube"
    assert item.external_id == "video-123"
    assert item.title == "Fresh trailer drop"
    assert item.summary == "Road update from production."
    assert item.canonical_url == "https://www.youtube.com/watch?v=video-123"
    assert item.thumbnail_url == "https://img.youtube.com/high.jpg"
    assert item.published_at == datetime(2026, 5, 18, 10, 15, tzinfo=timezone.utc)


def test_youtube_adapter_filters_existing_checkpoint_and_returns_oldest_first_for_delivery():
    adapter = YouTubeSyndicationAdapter(
        payload_loader=lambda: {
            "items": [
                {
                    "id": {"videoId": "video-300"},
                    "snippet": {
                        "title": "Newest clip",
                        "description": "Newest",
                        "publishedAt": "2026-05-18T12:00:00Z",
                    },
                },
                {
                    "contentDetails": {"videoId": "video-200"},
                    "snippet": {
                        "title": "Middle clip",
                        "description": "Middle",
                        "publishedAt": "2026-05-18T11:00:00Z",
                    },
                },
                {
                    "snippet": {
                        "title": "Known clip",
                        "description": "Known",
                        "publishedAt": "2026-05-18T10:00:00Z",
                        "resourceId": {"videoId": "video-100"},
                    }
                },
            ]
        }
    )

    result = adapter.fetch_since(checkpoint="video-100")

    assert result.next_checkpoint == "video-300"
    assert [item.external_id for item in result.items] == ["video-200", "video-300"]


def test_youtube_adapter_rejects_items_missing_required_fields():
    adapter = YouTubeSyndicationAdapter(
        payload_loader=lambda: {
            "items": [
                {
                    "snippet": {
                        "title": "Broken clip",
                        "publishedAt": "2026-05-18T10:00:00Z",
                    }
                }
            ]
        }
    )

    with pytest.raises(ValueError, match="videoId"):
        adapter.fetch_since()