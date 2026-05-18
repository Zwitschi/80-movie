"""Persistence adapters for bot-owned data will live here."""

from .syndication_repo import InMemorySyndicationSourceRepository

__all__ = ["InMemorySyndicationSourceRepository"]
