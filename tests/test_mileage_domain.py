from bot.omo_bot.commands import handle_mileage_adjust, handle_mileage_reverse
from bot.omo_bot.repositories import InMemoryMileageRepository
from bot.omo_bot.services.mileage_service import MileageConflictError, MileageService, MileageValidationError


def test_mileage_service_adjusts_totals_and_assigns_current_tier():
    service = MileageService(InMemoryMileageRepository())
    bronze = service.upsert_tier(
        guild_id=1, name='Bronze', points_required=10, sort_order=1)
    silver = service.upsert_tier(
        guild_id=1, name='Silver', points_required=25, sort_order=2)

    detail, event = service.adjust_user_mileage(
        guild_id=1,
        discord_user_id='u1',
        display_name='Alpha',
        points_delta=12,
        reason='Hosted screening',
        actor_user_id='operator-1',
    )

    assert event.event_type == 'manual_adjustment'
    assert detail.total.total_points == 12
    assert detail.total.current_tier_id == bronze.tier_id
    assert detail.current_tier is not None
    assert detail.current_tier.name == 'Bronze'

    detail, _ = service.adjust_user_mileage(
        guild_id=1,
        discord_user_id='u1',
        display_name='Alpha',
        points_delta=20,
        reason='Festival volunteer shift',
        actor_user_id='operator-1',
    )

    assert detail.total.total_points == 32
    assert detail.total.current_tier_id == silver.tier_id
    assert len(detail.events) == 2


def test_mileage_service_reverses_event_without_deleting_history():
    service = MileageService(InMemoryMileageRepository())
    service.upsert_tier(guild_id=1, name='Bronze',
                        points_required=5, sort_order=1)
    detail, event = service.adjust_user_mileage(
        guild_id=1,
        discord_user_id='u1',
        display_name='Alpha',
        points_delta=8,
        reason='Community cleanup',
        actor_user_id='operator-1',
    )

    assert detail.total.total_points == 8

    detail, reversal = service.reverse_event(
        guild_id=1,
        event_id=event.event_id,
        actor_user_id='operator-2',
        reason='Duplicate award',
    )

    assert reversal.event_type == 'manual_reversal'
    assert reversal.reversed_event_id == event.event_id
    assert detail.total.total_points == 0
    assert len(detail.events) == 2

    try:
        service.reverse_event(
            guild_id=1,
            event_id=event.event_id,
            actor_user_id='operator-3',
            reason='Second reversal',
        )
    except MileageConflictError:
        pass
    else:
        raise AssertionError('A mileage event should only be reversible once')


def test_mileage_service_filters_user_summaries_and_rejects_invalid_adjustments():
    service = MileageService(InMemoryMileageRepository())
    bronze = service.upsert_tier(
        guild_id=1, name='Bronze', points_required=5, sort_order=1)
    service.adjust_user_mileage(
        guild_id=1,
        discord_user_id='alpha-1',
        display_name='Alpha',
        points_delta=6,
        reason='Screening support',
    )
    service.adjust_user_mileage(
        guild_id=1,
        discord_user_id='beta-2',
        display_name='Beta',
        points_delta=2,
        reason='Checked in guests',
    )

    summaries = service.list_user_summaries(
        1, search='alp', tier_id=bronze.tier_id)
    assert len(summaries) == 1
    assert summaries[0].display_name == 'Alpha'

    try:
        service.adjust_user_mileage(
            guild_id=1,
            discord_user_id='gamma-3',
            display_name='Gamma',
            points_delta=0,
            reason='',
        )
    except MileageValidationError:
        pass
    else:
        raise AssertionError('Zero-delta mileage adjustment should fail')

    try:
        service.adjust_user_mileage(
            guild_id=1,
            discord_user_id='gamma-3',
            display_name='Gamma',
            points_delta=0,
            reason='Zero points',
        )
    except MileageValidationError:
        pass
    else:
        raise AssertionError('Adjustments with zero delta should be rejected')


def test_mileage_service_record_engagement():
    service = MileageService(InMemoryMileageRepository())

    # Test message engagement
    detail, event = service.record_engagement(
        guild_id=1,
        discord_user_id='u1',
        display_name='Alpha',
        engagement_type='message'
    )
    assert event.event_type == 'engagement_message'
    assert detail.total.total_points == 1  # Default for message

    # Test unknown engagement
    result = service.record_engagement(
        guild_id=1,
        discord_user_id='u1',
        display_name='Alpha',
        engagement_type='unknown'
    )
    assert result is None


def test_mileage_command_handlers_drive_adjust_and_reverse():
    service = MileageService(InMemoryMileageRepository())

    detail, event = handle_mileage_adjust(
        service,
        guild_id=1,
        discord_user_id='u1',
        display_name='Alpha',
        points_delta=7,
        reason='Community shift',
        actor_user_id='operator-1',
    )
    assert detail.total.total_points == 7

    detail, reversal = handle_mileage_reverse(
        service,
        guild_id=1,
        event_id=event.event_id,
        reason='Duplicate credit',
        actor_user_id='operator-2',
    )
    assert reversal.reversed_event_id == event.event_id
    assert detail.total.total_points == 0

