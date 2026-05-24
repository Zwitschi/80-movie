"""Compatibility shim for queue repository modules.

Import from the split modules directly:
- queue_repo_common  – protocol + row mappers
- queue_repo_memory  – InMemoryQueueRepository
- queue_repo_postgres – PostgresQueueRepository + builder
"""

from .queue_repo_common import QueueRepository, row_to_entry, row_to_event, row_to_summary
from .queue_repo_memory import InMemoryQueueRepository
from .queue_repo_postgres import PostgresQueueRepository, build_postgres_queue_repository

__all__ = [
    'QueueRepository',
    'InMemoryQueueRepository',
    'PostgresQueueRepository',
    'build_postgres_queue_repository',
    'row_to_entry',
    'row_to_event',
    'row_to_summary',
]
