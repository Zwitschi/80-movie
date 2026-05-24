"""Command (mutation) operations for queue service."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from ..models import QueueEntry, QueueEvent, QueueSnapshot, QueueSummary
from ..repositories import QueueRepository
from .queue_service_core import (
    QueueConflictError,
    QueueEntryNotFoundError,
    QueueNotFoundError,
    QueuePausedError,
    QueueValidationError,
    _assert_not_paused,
    _entry_payload,
    _utcnow,
)
from .queue_service_queries import QueueQueryMixin


class QueueCommandMixin(QueueQueryMixin):
    _repository: QueueRepository

    def ensure_queue(self, *, queue_id: str, guild_id: int, label: str) -> QueueSnapshot:
        snapshot = self._repository.get_queue(queue_id)
        if snapshot is not None:
            if snapshot.summary.guild_id != guild_id or snapshot.summary.label != label:
                updated_summary = replace(
                    snapshot.summary,
                    guild_id=guild_id,
                    label=label,
                )
                return self._repository.save_queue(summary=updated_summary, entries=snapshot.entries)
            return snapshot

        summary = QueueSummary(
            queue_id=queue_id,
            guild_id=guild_id,
            label=label,
            is_paused=False,
            paused_reason='',
            active_entry_id=None,
            waiting_count=0,
            total_entries=0,
            updated_at=_utcnow(),
        )
        return self._repository.save_queue(summary=summary, entries=())

    def join_queue(
        self,
        *,
        queue_id: str,
        guild_id: int,
        label: str,
        discord_user_id: str,
        display_name: str,
        actor_user_id: str | None = None,
        note: str = '',
    ) -> tuple[QueueSnapshot, QueueEvent]:
        snapshot = self.ensure_queue(
            queue_id=queue_id, guild_id=guild_id, label=label)
        _assert_not_paused(snapshot)
        if any(entry.discord_user_id == discord_user_id for entry in snapshot.entries):
            raise QueueConflictError("User is already in the queue")

        waiting_entries = self._waiting_entries(snapshot.entries)
        new_entry = QueueEntry(
            entry_id=str(uuid4()),
            queue_id=queue_id,
            discord_user_id=discord_user_id,
            display_name=display_name.strip() or discord_user_id,
            state='waiting',
            position=len(waiting_entries) + 1,
            note=note.strip(),
            joined_at=_utcnow(),
        )
        entries = self._sort_entries(snapshot.entries + (new_entry,))
        saved_snapshot = self._save_snapshot(snapshot.summary, entries)
        event = self._append_event(
            queue_id=queue_id,
            event_type='entry_joined',
            actor_user_id=actor_user_id,
            entry_id=new_entry.entry_id,
            payload={
                'entry_id': new_entry.entry_id,
                'discord_user_id': discord_user_id,
                'display_name': new_entry.display_name,
                'position': new_entry.position,
            },
        )
        return replace(saved_snapshot, last_event=event), event

    def leave_queue(
        self,
        *,
        queue_id: str,
        discord_user_id: str,
        actor_user_id: str | None = None,
        reason: str = '',
    ) -> tuple[QueueSnapshot, QueueEvent]:
        snapshot = self.get_queue(queue_id)
        entry = next(
            (item for item in snapshot.entries if item.discord_user_id == discord_user_id), None)
        if entry is None:
            raise QueueEntryNotFoundError("User is not currently in the queue")
        return self.remove_entry(
            queue_id=queue_id,
            entry_id=entry.entry_id,
            actor_user_id=actor_user_id,
            reason=reason or 'left queue',
        )

    def advance_queue(
        self,
        *,
        queue_id: str,
        actor_user_id: str | None = None,
    ) -> tuple[QueueSnapshot, QueueEvent]:
        snapshot = self.get_queue(queue_id)
        _assert_not_paused(snapshot)
        now = _utcnow()
        active_entry = self._active_entry(snapshot.entries)
        waiting_entries = self._waiting_entries(snapshot.entries)
        completed_entry_payload = None
        if active_entry is not None:
            completed_entry_payload = _entry_payload(active_entry)
        next_entry = waiting_entries[0] if waiting_entries else None
        next_entry_payload = None
        updated_entries = [
            entry for entry in snapshot.entries if active_entry is None or entry.entry_id != active_entry.entry_id]
        if next_entry is not None:
            updated_entries = [
                entry for entry in updated_entries if entry.entry_id != next_entry.entry_id]
            promoted_entry = replace(
                next_entry, state='active', position=0, started_at=now)
            updated_entries.append(promoted_entry)
            next_entry_payload = _entry_payload(promoted_entry)
        entries = self._resequence_entries(tuple(updated_entries))
        saved_snapshot = self._save_snapshot(snapshot.summary, entries)
        event = self._append_event(
            queue_id=queue_id,
            event_type='queue_advanced',
            actor_user_id=actor_user_id,
            entry_id=next_entry.entry_id if next_entry is not None else None,
            payload={
                'completed_entry': completed_entry_payload,
                'activated_entry': next_entry_payload,
            },
        )
        return replace(saved_snapshot, last_event=event), event

    def remove_entry(
        self,
        *,
        queue_id: str,
        entry_id: str,
        actor_user_id: str | None = None,
        reason: str = '',
    ) -> tuple[QueueSnapshot, QueueEvent]:
        snapshot = self.get_queue(queue_id)
        entry = next(
            (item for item in snapshot.entries if item.entry_id == entry_id), None)
        if entry is None:
            raise QueueEntryNotFoundError(
                f"Queue entry '{entry_id}' was not found")
        updated_entries = tuple(
            item for item in snapshot.entries if item.entry_id != entry_id)
        saved_snapshot = self._save_snapshot(
            snapshot.summary, self._resequence_entries(updated_entries))
        event = self._append_event(
            queue_id=queue_id,
            event_type='entry_removed',
            actor_user_id=actor_user_id,
            entry_id=entry.entry_id,
            payload={
                'entry': _entry_payload(entry),
                'reason': reason.strip(),
            },
        )
        return replace(saved_snapshot, last_event=event), event

    def move_entry(
        self,
        *,
        queue_id: str,
        entry_id: str,
        target_position: int,
        actor_user_id: str | None = None,
        reason: str = '',
    ) -> tuple[QueueSnapshot, QueueEvent]:
        snapshot = self.get_queue(queue_id)
        _assert_not_paused(snapshot)
        waiting_entries = list(self._waiting_entries(snapshot.entries))
        source_index = next((index for index, entry in enumerate(
            waiting_entries) if entry.entry_id == entry_id), None)
        if source_index is None:
            raise QueueEntryNotFoundError(
                f"Queue entry '{entry_id}' was not found")
        if target_position < 1 or target_position > len(waiting_entries):
            raise QueueValidationError(
                'Target position is outside the waiting queue range')
        entry = waiting_entries.pop(source_index)
        waiting_entries.insert(target_position - 1, entry)
        active_entry = self._active_entry(snapshot.entries)
        reordered_entries = tuple(
            ([active_entry] if active_entry else []) + waiting_entries)
        saved_snapshot = self._save_snapshot(
            snapshot.summary, self._resequence_entries(reordered_entries))
        event = self._append_event(
            queue_id=queue_id,
            event_type='entry_moved',
            actor_user_id=actor_user_id,
            entry_id=entry.entry_id,
            payload={
                'entry': _entry_payload(entry),
                'target_position': target_position,
                'reason': reason.strip(),
            },
        )
        return replace(saved_snapshot, last_event=event), event

    def pause_queue(
        self,
        *,
        queue_id: str,
        actor_user_id: str | None = None,
        reason: str = '',
    ) -> tuple[QueueSnapshot, QueueEvent]:
        snapshot = self.get_queue(queue_id)
        if snapshot.summary.is_paused:
            raise QueueConflictError('Queue is already paused')
        updated_summary = replace(
            snapshot.summary, is_paused=True, paused_reason=reason.strip())
        saved_snapshot = self._save_snapshot(updated_summary, snapshot.entries)
        event = self._append_event(
            queue_id=queue_id,
            event_type='queue_paused',
            actor_user_id=actor_user_id,
            entry_id=None,
            payload={'reason': reason.strip()},
        )
        return replace(saved_snapshot, last_event=event), event

    def resume_queue(
        self,
        *,
        queue_id: str,
        actor_user_id: str | None = None,
    ) -> tuple[QueueSnapshot, QueueEvent]:
        snapshot = self.get_queue(queue_id)
        if not snapshot.summary.is_paused:
            raise QueueConflictError('Queue is not paused')
        updated_summary = replace(
            snapshot.summary, is_paused=False, paused_reason='')
        saved_snapshot = self._save_snapshot(updated_summary, snapshot.entries)
        event = self._append_event(
            queue_id=queue_id,
            event_type='queue_resumed',
            actor_user_id=actor_user_id,
            entry_id=None,
            payload={},
        )
        return replace(saved_snapshot, last_event=event), event

    def clear_queue(
        self,
        *,
        queue_id: str,
        actor_user_id: str | None = None,
        reason: str = '',
        dry_run: bool = False,
    ) -> tuple[QueueSnapshot, QueueEvent]:
        from datetime import datetime, timezone
        snapshot = self.get_queue(queue_id)
        removed_entries = [_entry_payload(
            entry) for entry in snapshot.entries]
        if dry_run:
            preview_event = QueueEvent(
                event_id='dry-run',
                queue_id=queue_id,
                event_type='queue_cleared',
                actor_user_id=actor_user_id,
                entry_id=None,
                payload={
                    'removed_entries': removed_entries,
                    'reason': reason.strip(),
                    'dry_run': True,
                },
                created_at=datetime.now(tz=timezone.utc),
            )
            return replace(snapshot, last_event=preview_event), preview_event
        saved_snapshot = self._save_snapshot(snapshot.summary, ())
        event = self._append_event(
            queue_id=queue_id,
            event_type='queue_cleared',
            actor_user_id=actor_user_id,
            entry_id=None,
            payload={
                'removed_entries': removed_entries,
                'reason': reason.strip(),
            },
        )
        return replace(saved_snapshot, last_event=event), event

    def _save_snapshot(
        self,
        summary: QueueSummary,
        entries: tuple[QueueEntry, ...],
    ) -> QueueSnapshot:
        entries = self._resequence_entries(entries)
        active_entry = self._active_entry(entries)
        updated_summary = replace(
            summary,
            active_entry_id=active_entry.entry_id if active_entry else None,
            waiting_count=len(self._waiting_entries(entries)),
            total_entries=len(entries),
            updated_at=_utcnow(),
        )
        return self._repository.save_queue(summary=updated_summary, entries=entries)

    def _append_event(
        self,
        *,
        queue_id: str,
        event_type: str,
        actor_user_id: str | None,
        entry_id: str | None,
        payload: dict[str, object],
    ) -> QueueEvent:
        return self._repository.append_event(
            QueueEvent(
                event_id=str(uuid4()),
                queue_id=queue_id,
                event_type=event_type,
                actor_user_id=actor_user_id,
                entry_id=entry_id,
                payload=payload,
                created_at=_utcnow(),
            )
        )

    def _resequence_entries(self, entries: tuple[QueueEntry, ...]) -> tuple[QueueEntry, ...]:
        active_entry = self._active_entry(entries)
        waiting_entries = list(self._waiting_entries(entries))
        resequenced: list[QueueEntry] = []
        if active_entry is not None:
            resequenced.append(replace(active_entry, position=0))
        for index, entry in enumerate(waiting_entries, start=1):
            resequenced.append(replace(entry, position=index))
        return tuple(resequenced)
