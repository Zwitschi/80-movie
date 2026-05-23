"""Queue domain service for moderator and command operations.

Thin facade that composes query + command mixins.
"""

from __future__ import annotations

from ..repositories import QueueRepository
from .queue_service_commands import QueueCommandMixin
from .queue_service_core import (
    QueueConflictError,
    QueueEntryNotFoundError,
    QueueError,
    QueueNotFoundError,
    QueuePausedError,
    QueueValidationError,
)
from .queue_service_queries import QueueQueryMixin


class QueueService(QueueCommandMixin):
    def __init__(self, repository: QueueRepository) -> None:
        self._repository = repository


__all__ = [
    'QueueService',
    'QueueError',
    'QueueNotFoundError',
    'QueuePausedError',
    'QueueConflictError',
    'QueueEntryNotFoundError',
    'QueueValidationError',
]
