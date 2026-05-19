"""Compatibility shim for legacy website import path.

Live bot content repository implementation now lives in control_room.
"""

from control_room.bot_content_repo import *  # noqa: F401,F403
