"""Content store abstractions for reading and writing site content.

Supports both Flask app context and standalone usage.
"""

from . import content_store_db


class ContentReadError(RuntimeError):
    """Raised when content cannot be read."""
    pass


class ContentWriteError(RuntimeError):
    """Raised when content cannot be written."""
    pass


def get_content_reader(flask_app=None):
    """Get content reader instance."""
    return content_store_db.get_content_reader(flask_app)


def get_content_writer(flask_app=None):
    """Get content writer instance."""
    return content_store_db.get_content_writer(flask_app)
