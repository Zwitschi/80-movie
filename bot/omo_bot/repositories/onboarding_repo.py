"""Compatibility shim for onboarding repository modules.

Import from the split modules directly:
- onboarding_repo_common  – protocol + row mappers
- onboarding_repo_memory  – InMemoryOnboardingRepository
- onboarding_repo_postgres – PostgresOnboardingRepository + builder
"""

from .onboarding_repo_common import OnboardingRepository, row_to_event
from .onboarding_repo_memory import InMemoryOnboardingRepository
from .onboarding_repo_postgres import PostgresOnboardingRepository, build_postgres_onboarding_repository

__all__ = [
    'OnboardingRepository',
    'InMemoryOnboardingRepository',
    'PostgresOnboardingRepository',
    'build_postgres_onboarding_repository',
    'row_to_event',
]
