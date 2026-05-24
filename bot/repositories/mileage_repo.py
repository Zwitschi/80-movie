"""Compatibility shim for mileage repository modules.

Import from the split modules directly:
- mileage_repo_common  – protocol + row mappers
- mileage_repo_memory  – InMemoryMileageRepository
- mileage_repo_postgres – PostgresMileageRepository + builder
"""

from .mileage_repo_common import MileageRepository, row_to_event, row_to_tier, row_to_total
from .mileage_repo_memory import InMemoryMileageRepository
from .mileage_repo_postgres import PostgresMileageRepository, build_postgres_mileage_repository

__all__ = [
    'MileageRepository',
    'InMemoryMileageRepository',
    'PostgresMileageRepository',
    'build_postgres_mileage_repository',
    'row_to_event',
    'row_to_tier',
    'row_to_total',
]
