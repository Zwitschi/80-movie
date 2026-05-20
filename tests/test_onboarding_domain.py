import pytest
from bot.omo_bot.models.onboarding import OnboardingStatus
from bot.omo_bot.repositories.onboarding_repo import InMemoryOnboardingRepository
from bot.omo_bot.services.onboarding_service import OnboardingService


def test_onboarding_service_lifecycle():
    repo = InMemoryOnboardingRepository()
    service = OnboardingService(repo)

    guild_id = 123
    user_id = "u1"

    # 1. Member join
    state = service.handle_member_join(
        guild_id=guild_id, discord_user_id=user_id)
    assert state.status == OnboardingStatus.PENDING
    assert state.discord_user_id == user_id

    # 2. Start onboarding
    state = service.start_onboarding(
        guild_id=guild_id, discord_user_id=user_id)
    assert state.status == OnboardingStatus.IN_PROGRESS

    # 3. Record role assignment
    state = service.record_role_assigned(
        guild_id=guild_id, discord_user_id=user_id, role_id=456)
    assert 456 in state.metadata["assigned_roles"]

    # 4. Complete onboarding
    state = service.complete_onboarding(
        guild_id=guild_id, discord_user_id=user_id)
    assert state.status == OnboardingStatus.COMPLETED
    assert state.onboarded_at is not None


def test_onboarding_service_rejoin_preserves_state():
    repo = InMemoryOnboardingRepository()
    service = OnboardingService(repo)

    guild_id = 123
    user_id = "u1"

    service.handle_member_join(guild_id=guild_id, discord_user_id=user_id)
    service.start_onboarding(guild_id=guild_id, discord_user_id=user_id)

    # Rejoin
    state = service.handle_member_join(
        guild_id=guild_id, discord_user_id=user_id)
    assert state.status == OnboardingStatus.IN_PROGRESS
