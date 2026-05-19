"""Compatibility shim for legacy website import path.

Live bot operator service implementation now lives in control_room.
"""

from control_room.bot_operator_service import *  # noqa: F401,F403
