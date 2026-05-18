"""Repository seams for bot syndication source state."""

from __future__ import annotations

from dataclasses import replace

from ..models import SyndicationSourceState


class InMemorySyndicationSourceRepository:
    """Simple repository used to exercise syndication state without a DB."""

    def __init__(self, initial_states: list[SyndicationSourceState] | None = None) -> None:
        self._states = {
            state.source_key: replace(state)
            for state in (initial_states or [])
        }

    def get_by_source_key(self, source_key: str) -> SyndicationSourceState | None:
        state = self._states.get(source_key)
        return replace(state) if state is not None else None

    def save(self, state: SyndicationSourceState) -> SyndicationSourceState:
        stored_state = replace(state)
        self._states[state.source_key] = stored_state
        return replace(stored_state)
