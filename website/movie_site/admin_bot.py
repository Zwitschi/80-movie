"""Compatibility shim for legacy website import path.

Live admin bot implementation now lives in control_room.admin_bot.
"""

from control_room.admin_bot import *  # noqa: F401,F403
