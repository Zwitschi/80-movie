from bot.omo_bot.commands import handle_queue_advance, handle_queue_join, handle_queue_leave
from bot.omo_bot.repositories import InMemoryQueueRepository
from bot.omo_bot.services.queue_service import QueueConflictError, QueuePausedError, QueueService


def test_queue_service_join_and_advance_promotes_next_entry():
    service = QueueService(InMemoryQueueRepository())

    snapshot, _ = service.join_queue(
        queue_id='guild-1:open-mic',
        guild_id=1,
        label='Open Mic',
        discord_user_id='u1',
        display_name='Alpha',
        actor_user_id='operator-1',
    )
    snapshot, _ = service.join_queue(
        queue_id='guild-1:open-mic',
        guild_id=1,
        label='Open Mic',
        discord_user_id='u2',
        display_name='Beta',
        actor_user_id='operator-1',
    )

    assert snapshot.summary.waiting_count == 2
    assert [entry.position for entry in snapshot.entries] == [1, 2]

    snapshot, event = service.advance_queue(
        queue_id='guild-1:open-mic',
        actor_user_id='operator-1',
    )

    assert event.event_type == 'queue_advanced'
    assert snapshot.summary.active_entry_id is not None
    assert snapshot.summary.waiting_count == 1
    assert snapshot.entries[0].state == 'active'
    assert snapshot.entries[0].display_name == 'Alpha'
    assert snapshot.entries[0].position == 0
    assert snapshot.entries[1].display_name == 'Beta'
    assert snapshot.entries[1].position == 1


def test_queue_service_move_remove_and_clear_resequence_waiting_entries():
    service = QueueService(InMemoryQueueRepository())
    for user_id, display_name in [('u1', 'Alpha'), ('u2', 'Beta'), ('u3', 'Gamma')]:
        service.join_queue(
            queue_id='guild-1:showcase',
            guild_id=1,
            label='Showcase',
            discord_user_id=user_id,
            display_name=display_name,
        )

    snapshot = service.get_queue('guild-1:showcase')
    moved_entry_id = snapshot.entries[2].entry_id
    snapshot, _ = service.move_entry(
        queue_id='guild-1:showcase',
        entry_id=moved_entry_id,
        target_position=1,
        actor_user_id='operator-1',
        reason='priority slot',
    )

    assert [entry.display_name for entry in snapshot.entries] == [
        'Gamma', 'Alpha', 'Beta']
    assert [entry.position for entry in snapshot.entries] == [1, 2, 3]

    snapshot, _ = service.remove_entry(
        queue_id='guild-1:showcase',
        entry_id=snapshot.entries[1].entry_id,
        actor_user_id='operator-1',
        reason='no show',
    )

    assert [entry.display_name for entry in snapshot.entries] == [
        'Gamma', 'Beta']
    assert [entry.position for entry in snapshot.entries] == [1, 2]

    snapshot, event = service.clear_queue(
        queue_id='guild-1:showcase',
        actor_user_id='operator-1',
        reason='event closed',
    )

    assert snapshot.entries == ()
    assert snapshot.summary.total_entries == 0
    assert event.event_type == 'queue_cleared'
    assert len(event.payload['removed_entries']) == 2


def test_queue_service_rejects_duplicate_join_and_paused_queue_writes():
    service = QueueService(InMemoryQueueRepository())
    service.join_queue(
        queue_id='guild-1:late-night',
        guild_id=1,
        label='Late Night',
        discord_user_id='u1',
        display_name='Alpha',
    )

    try:
        service.join_queue(
            queue_id='guild-1:late-night',
            guild_id=1,
            label='Late Night',
            discord_user_id='u1',
            display_name='Alpha',
        )
    except QueueConflictError:
        pass
    else:
        raise AssertionError('Duplicate queue join should fail')

    service.pause_queue(queue_id='guild-1:late-night',
                        actor_user_id='operator-1', reason='reset')

    try:
        service.join_queue(
            queue_id='guild-1:late-night',
            guild_id=1,
            label='Late Night',
            discord_user_id='u2',
            display_name='Beta',
        )
    except QueuePausedError:
        pass
    else:
        raise AssertionError('Queue join should fail while paused')


def test_queue_command_handlers_drive_queue_service():
    service = QueueService(InMemoryQueueRepository())

    snapshot, _ = handle_queue_join(
        service,
        queue_id='guild-2:feature',
        guild_id=2,
        label='Feature Set',
        discord_user_id='u1',
        display_name='Alpha',
        actor_user_id='operator-1',
    )
    assert snapshot.summary.total_entries == 1

    snapshot, _ = handle_queue_advance(
        service,
        queue_id='guild-2:feature',
        actor_user_id='operator-1',
    )
    assert snapshot.entries[0].state == 'active'

    snapshot, _ = handle_queue_leave(
        service,
        queue_id='guild-2:feature',
        discord_user_id='u1',
        actor_user_id='operator-1',
    )
    assert snapshot.summary.total_entries == 0

