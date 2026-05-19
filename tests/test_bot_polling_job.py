from datetime import datetime, timedelta, timezone
import json
from io import BytesIO

import pytest

from bot.omo_bot.adapters import SyndicationAdapter
from bot.omo_bot.config import BotConfig
from bot.omo_bot.jobs import SyndicationPollingJob
from bot.omo_bot.models import SyndicationFetchResult, SyndicationItem, SyndicationSourceState
from bot.omo_bot.repositories import InMemorySyndicationSourceRepository
from bot.omo_bot.services import SyndicationDeliveryBatch, SyndicationPlanningService
from bot.omo_bot.services import DiscordApiSyndicationDeliverySink


class RecordingDeliverySink:
    def __init__(self) -> None:
        self.batches: list[SyndicationDeliveryBatch] = []

    def deliver(self, batch: SyndicationDeliveryBatch) -> None:
        self.batches.append(batch)


class FailingDeliverySink:
    def deliver(self, batch: SyndicationDeliveryBatch) -> None:
        raise RuntimeError("delivery failed")


class FakeAdapter:
    source_key = "youtube"

    def __init__(self, result: SyndicationFetchResult) -> None:
        self.result = result
        self.calls: list[str | None] = []

    def fetch_since(self, *, checkpoint: str | None = None) -> SyndicationFetchResult:
        self.calls.append(checkpoint)
        return self.result


def _build_config() -> BotConfig:
    return BotConfig.from_env(
        {
            "OMO_DISCORD_TOKEN": "token-value",
            "OMO_SYNDICATION_SOURCES": "youtube",
            "OMO_SYNDICATION_POLL_SECONDS": "300",
        }
    )


def test_syndication_polling_job_delivers_new_items_and_updates_checkpoint():
    now = datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc)
    repository = InMemorySyndicationSourceRepository(
        [SyndicationSourceState(source_key="youtube", checkpoint="video-100")]
    )
    planning_service = SyndicationPlanningService(
        config=_build_config(), repository=repository)
    item = SyndicationItem(
        source_key="youtube",
        external_id="video-200",
        title="Fresh clip",
        canonical_url="https://www.youtube.com/watch?v=video-200",
        published_at=now - timedelta(minutes=5),
    )
    adapter: SyndicationAdapter = FakeAdapter(
        SyndicationFetchResult(items=(item,), next_checkpoint="video-200")
    )
    delivery_sink = RecordingDeliverySink()
    job = SyndicationPollingJob(
        planning_service=planning_service,
        repository=repository,
        adapters={"youtube": adapter},
        delivery_sink=delivery_sink,
    )

    result = job.run(now=now)

    assert result.polled_sources == ("youtube",)
    assert result.delivered_items == 1
    assert result.failed_sources == ()
    assert adapter.calls == ["video-100"]
    assert len(delivery_sink.batches) == 1
    assert delivery_sink.batches[0].items == (item,)

    saved_state = repository.get_by_source_key("youtube")
    assert saved_state is not None
    assert saved_state.checkpoint == "video-200"
    assert saved_state.last_polled_at == now
    assert saved_state.last_succeeded_at == now
    assert saved_state.last_failed_at is None


def test_syndication_polling_job_marks_failure_when_delivery_raises():
    now = datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc)
    repository = InMemorySyndicationSourceRepository(
        [SyndicationSourceState(source_key="youtube", checkpoint="video-100")]
    )
    planning_service = SyndicationPlanningService(
        config=_build_config(), repository=repository)
    item = SyndicationItem(
        source_key="youtube",
        external_id="video-200",
        title="Fresh clip",
        canonical_url="https://www.youtube.com/watch?v=video-200",
        published_at=now - timedelta(minutes=5),
    )
    job = SyndicationPollingJob(
        planning_service=planning_service,
        repository=repository,
        adapters={
            "youtube": FakeAdapter(
                SyndicationFetchResult(
                    items=(item,), next_checkpoint="video-200")
            )
        },
        delivery_sink=FailingDeliverySink(),
    )

    with pytest.raises(RuntimeError, match="delivery failed"):
        job.run(now=now)

    saved_state = repository.get_by_source_key("youtube")
    assert saved_state is not None
    assert saved_state.checkpoint == "video-100"
    assert saved_state.last_polled_at == now
    assert saved_state.last_succeeded_at is None
    assert saved_state.last_failed_at == now


def test_build_runtime_wires_polling_job_and_delivery_contract():
    from bot.omo_bot.main import build_runtime
    import logging

    runtime = build_runtime(_build_config(), logging.getLogger("test-bot"))

    snapshot = runtime.health_snapshot()
    assert snapshot["syndication_polling_job"] == "SyndicationPollingJob"
    assert snapshot["syndication_delivery_backend"] == "NullSyndicationDeliverySink"


def test_discord_delivery_sink_posts_items_to_configured_channel(monkeypatch):
    captured: list[tuple[str, dict[str, str], dict[str, object]]] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout=10):
        captured.append(
            (
                request.full_url,
                dict(request.header_items()),
                json.loads(request.data.decode("utf-8")),
            )
        )
        return FakeResponse()

    monkeypatch.setattr("bot.omo_bot.services.delivery.urlopen", fake_urlopen)
    sink = DiscordApiSyndicationDeliverySink(
        bot_token="token-value",
        channel_map={"announcements": 200},
    )
    batch = SyndicationDeliveryBatch(
        source_key="youtube",
        items=(
            SyndicationItem(
                source_key="youtube",
                external_id="video-200",
                title="Fresh clip",
                canonical_url="https://www.youtube.com/watch?v=video-200",
                published_at=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc),
                summary="New upload",
            ),
        ),
    )

    sink.deliver(batch)

    assert len(captured) == 1
    url, headers, payload = captured[0]
    assert url.endswith("/channels/200/messages")
    assert headers["Authorization"] == "Bot token-value"
    assert payload["allowed_mentions"] == {"parse": []}
    assert "Fresh clip" in payload["content"]
    assert "https://www.youtube.com/watch?v=video-200" in payload["content"]
