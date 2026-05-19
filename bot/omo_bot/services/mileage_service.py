"""Mileage / XP service logic."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from ..models import MileageEvent, MileageTier, MileageTierStat, MileageTotal, MileageUserDetail
from ..repositories import MileageRepository


class MileageError(RuntimeError):
    pass


class MileageNotFoundError(MileageError):
    pass


class MileageConflictError(MileageError):
    pass


class MileageValidationError(MileageError):
    pass


class MileageService:
    def __init__(self, repository: MileageRepository) -> None:
        self._repository = repository

    def list_tiers(self, guild_id: int) -> tuple[MileageTier, ...]:
        return self._repository.list_tiers(guild_id)

    def upsert_tier(
        self,
        *,
        guild_id: int,
        name: str,
        points_required: int,
        role_id: int | None = None,
        sort_order: int = 0,
        tier_id: str | None = None,
    ) -> MileageTier:
        resolved_name = name.strip()
        if not resolved_name:
            raise MileageValidationError('Tier name is required.')
        if points_required < 0:
            raise MileageValidationError(
                'Tier threshold must be zero or greater.')
        return self._repository.upsert_tier(
            MileageTier(
                tier_id=tier_id or str(uuid4()),
                guild_id=guild_id,
                name=resolved_name,
                points_required=points_required,
                role_id=role_id,
                sort_order=sort_order,
                updated_at=self._utcnow(),
            )
        )

    def list_user_summaries(
        self,
        guild_id: int,
        *,
        search: str = '',
        tier_id: str | None = None,
    ) -> tuple[MileageTotal, ...]:
        return self._repository.list_user_totals(guild_id, search=search, tier_id=tier_id)

    def get_user_detail(
        self,
        guild_id: int,
        discord_user_id: str,
        *,
        limit: int = 20,
    ) -> MileageUserDetail:
        total = self._repository.get_user_total(guild_id, discord_user_id)
        if total is None:
            raise MileageNotFoundError(
                f"Mileage user '{discord_user_id}' was not found")
        tiers = self._repository.list_tiers(guild_id)
        current_tier = next(
            (tier for tier in tiers if tier.tier_id == total.current_tier_id), None)
        events = self._repository.list_user_events(
            guild_id, discord_user_id, limit=limit)
        return MileageUserDetail(total=total, current_tier=current_tier, events=events)

    def list_tier_stats(self, guild_id: int) -> tuple[MileageTierStat, ...]:
        tiers = self._repository.list_tiers(guild_id)
        totals = self._repository.list_user_totals(guild_id)
        counts = {tier.tier_id: 0 for tier in tiers}
        for total in totals:
            if total.current_tier_id in counts:
                counts[total.current_tier_id] += 1
        return tuple(MileageTierStat(tier=tier, user_count=counts.get(tier.tier_id, 0)) for tier in tiers)

    def adjust_user_mileage(
        self,
        *,
        guild_id: int,
        discord_user_id: str,
        display_name: str,
        points_delta: int,
        reason: str,
        actor_user_id: str | None = None,
        correlation_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> tuple[MileageUserDetail, MileageEvent]:
        resolved_reason = reason.strip()
        if points_delta == 0:
            raise MileageValidationError(
                'Mileage adjustment delta must not be zero.')
        if not resolved_reason:
            raise MileageValidationError(
                'Mileage adjustment reason is required.')
        resolved_user_id = str(discord_user_id).strip()
        if not resolved_user_id:
            raise MileageValidationError('discord_user_id is required.')
        event = self._repository.append_event(
            MileageEvent(
                event_id=str(uuid4()),
                guild_id=guild_id,
                discord_user_id=resolved_user_id,
                display_name=display_name.strip() or resolved_user_id,
                event_type='manual_adjustment',
                points_delta=points_delta,
                reason=resolved_reason,
                actor_user_id=actor_user_id,
                correlation_id=correlation_id.strip() if isinstance(
                    correlation_id, str) and correlation_id.strip() else None,
                reversed_event_id=None,
                metadata=dict(metadata or {}),
                created_at=self._utcnow(),
            )
        )
        total = self._apply_event_to_total(event)
        detail = self.get_user_detail(guild_id, resolved_user_id)
        return replace(detail, total=total), event

    def reverse_event(
        self,
        *,
        guild_id: int,
        event_id: str,
        actor_user_id: str | None = None,
        reason: str,
    ) -> tuple[MileageUserDetail, MileageEvent]:
        resolved_reason = reason.strip()
        if not resolved_reason:
            raise MileageValidationError(
                'Mileage reversal reason is required.')
        original_event = self._repository.get_event(event_id)
        if original_event is None or original_event.guild_id != guild_id:
            raise MileageNotFoundError(
                f"Mileage event '{event_id}' was not found")
        if original_event.reversed_event_id is not None:
            raise MileageConflictError(
                'Mileage reversal events cannot be reversed again.')
        if self._repository.has_reversal_for(event_id):
            raise MileageConflictError(
                'Mileage event has already been reversed.')

        reversal_event = self._repository.append_event(
            MileageEvent(
                event_id=str(uuid4()),
                guild_id=guild_id,
                discord_user_id=original_event.discord_user_id,
                display_name=original_event.display_name,
                event_type='manual_reversal',
                points_delta=-original_event.points_delta,
                reason=resolved_reason,
                actor_user_id=actor_user_id,
                correlation_id=original_event.correlation_id,
                reversed_event_id=original_event.event_id,
                metadata={
                    'reversed_event_id': original_event.event_id,
                    'reversed_event_type': original_event.event_type,
                },
                created_at=self._utcnow(),
            )
        )
        total = self._apply_event_to_total(reversal_event)
        detail = self.get_user_detail(guild_id, original_event.discord_user_id)
        return replace(detail, total=total), reversal_event

    def _apply_event_to_total(self, event: MileageEvent) -> MileageTotal:
        previous_total = self._repository.get_user_total(
            event.guild_id, event.discord_user_id)
        total_points = (
            previous_total.total_points if previous_total is not None else 0) + event.points_delta
        display_name = event.display_name or (
            previous_total.display_name if previous_total is not None else event.discord_user_id)
        tiers = self._repository.list_tiers(event.guild_id)
        current_tier = self._resolve_current_tier(tiers, total_points)
        saved_total = self._repository.save_user_total(
            MileageTotal(
                guild_id=event.guild_id,
                discord_user_id=event.discord_user_id,
                display_name=display_name,
                total_points=total_points,
                current_tier_id=current_tier.tier_id if current_tier else None,
                current_tier_name=current_tier.name if current_tier else None,
                last_event_id=event.event_id,
                last_event_at=event.created_at,
                updated_at=self._utcnow(),
            )
        )
        return saved_total

    @staticmethod
    def _resolve_current_tier(
        tiers: tuple[MileageTier, ...],
        total_points: int,
    ) -> MileageTier | None:
        eligible = [
            tier for tier in tiers if tier.points_required <= total_points]
        if not eligible:
            return None
        eligible.sort(key=lambda tier: (tier.points_required,
                      tier.sort_order, tier.name.lower(), tier.tier_id))
        return eligible[-1]

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)
