"""Content store abstractions — delegates to shared.content_store."""

from shared.content_store import (
    ContentReadError,
    ContentWriteError,
    get_content_reader,
    get_content_writer,
)

__all__ = [
    'ContentReadError',
    'ContentWriteError',
    'get_content_reader',
    'get_content_writer',
]
