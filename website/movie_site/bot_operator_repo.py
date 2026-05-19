"""Compatibility shim for legacy website import path.

Live bot operator repository implementation now lives in control_room.
"""

from control_room.bot_operator_repo import *  # noqa: F401,F403
