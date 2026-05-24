"""Service seam for append-only bot audit entries."""

from __future__ import annotations

from ..repositories.audit_repo import BotAuditLogEntry, BotAuditLogRepository


class BotAuditService:
    def __init__(self, repository: BotAuditLogRepository) -> None:
        self._repository = repository

    def record(
        self,
        *,
        actor_user_id: str | None,
        actor_session_id: str | None,
        action_key: str,
        target_type: str,
        target_key: str,
        request_id: str | None,
        before_state: dict[str, object] | None,
        after_state: dict[str, object] | None,
    ) -> BotAuditLogEntry:
        return self._repository.append(
            BotAuditLogEntry(
                actor_user_id=actor_user_id,
                actor_session_id=actor_session_id,
                action_key=action_key,
                target_type=target_type,
                target_key=target_key,
                request_id=request_id,
                before_state=before_state,
                after_state=after_state,
            )
        )
