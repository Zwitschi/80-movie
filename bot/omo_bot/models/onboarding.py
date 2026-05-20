"""Onboarding domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class OnboardingStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass(frozen=True)
class OnboardingUserState:
    guild_id: int
    discord_user_id: str
    status: OnboardingStatus
    joined_at: datetime
    onboarded_at: datetime | None = None
    metadata: dict[str, object] = None

    def __post_init__(self):
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})
