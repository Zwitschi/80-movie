import pytest
from bot.omo_bot.models.onboarding import OnboardingStatus, OnboardingUserState
from bot.omo_bot.repositories.onboarding_repo import InMemoryOnboardingRepository
from bot.omo_bot.repositories.queue_repo import InMemoryQueueRepository
from bot.omo_bot.repositories.mileage_repo import InMemoryMileageRepository
from bot.omo_bot.services.onboarding_service import OnboardingService
from bot.omo_bot.services.queue_service import QueueService
from bot.omo_bot.services.mileage_service import MileageService
from bot.omo_bot.services.moderation_service import ModerationService
from datetime import datetime, timezone


def test_moderation_reset_onboarding():
    onboarding_repo = InMemoryOnboardingRepository()
    queue_repo = InMemoryQueueRepository()
    mileage_repo = InMemoryMileageRepository()

    onboarding_service = OnboardingService(onboarding_repo)
    queue_service = QueueService(queue_repo)
    mileage_service = MileageService(mileage_repo)

    moderation_service = ModerationService(
        queue_service=queue_service,
        mileage_service=mileage_service,
        onboarding_service=onboarding_service,
        onboarding_repository=onboarding_repo
    )

    guild_id = 123
    user_id = "u1"

    # Set user to completed
    onboarding_repo.save_user_state(OnboardingUserState(
        guild_id=guild_id,
        discord_user_id=user_id,
        status=OnboardingStatus.COMPLETED,
        joined_at=datetime.now(timezone.utc),
        onboarded_at=datetime.now(timezone.utc)
    ))

    # Reset
    moderation_service.reset_user_onboarding(
        guild_id=guild_id,
        discord_user_id=user_id,
        actor_user_id="mod-1",
        reason="Test reset"
    )

    state = onboarding_repo.get_user_state(guild_id, user_id)
    assert state.status == OnboardingStatus.PENDING
    assert state.onboarded_at is None


def test_moderation_cleanup_queue():
    onboarding_repo = InMemoryOnboardingRepository()
    queue_repo = InMemoryQueueRepository()
    mileage_repo = InMemoryMileageRepository()

    onboarding_service = OnboardingService(onboarding_repo)
    queue_service = QueueService(queue_repo)
    mileage_service = MileageService(mileage_repo)

    moderation_service = ModerationService(
        queue_service=queue_service,
        mileage_service=mileage_service,
        onboarding_service=onboarding_service,
        onboarding_repository=onboarding_repo
    )

    queue_id = "test-q"
    queue_service.ensure_queue(queue_id=queue_id, guild_id=123, label="Test")
    queue_service.join_queue(queue_id=queue_id, guild_id=123,
                             label="Test", discord_user_id="u1", display_name="User 1")

    snapshot = queue_service.get_queue(queue_id)
    assert len(snapshot.entries) == 1

    # Cleanup
    moderation_service.cleanup_queue(queue_id=queue_id, actor_user_id="mod-1")

    snapshot = queue_service.get_queue(queue_id)
    assert len(snapshot.entries) == 0
