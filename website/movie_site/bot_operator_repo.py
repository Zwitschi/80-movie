from __future__ import annotations

from datetime import datetime
from typing import Any

from .db import get_conn, get_dict_cursor


def _bot_operator_table_exists() -> bool:
    cursor = get_dict_cursor()
    try:
        cursor.execute(
            "SELECT to_regclass('public.bot_operator') AS table_name")
        table_row = cursor.fetchone()
        return bool(table_row and table_row.get('table_name'))
    finally:
        cursor.close()


def get_bot_operator_by_discord_user_id(user_id: str) -> dict[str, Any] | None:
    if not _bot_operator_table_exists():
        return None

    cursor = get_dict_cursor()
    try:
        cursor.execute(
            "SELECT discord_user_id, username, global_name, avatar_url, scopes, is_active, last_login_at "
            "FROM bot_operator WHERE discord_user_id = %s",
            (user_id,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()


def list_bot_operators() -> list[dict[str, Any]]:
    if not _bot_operator_table_exists():
        return []

    cursor = get_dict_cursor()
    try:
        cursor.execute(
            "SELECT discord_user_id, username, global_name, avatar_url, scopes, is_active, last_login_at "
            "FROM bot_operator "
            "ORDER BY COALESCE(global_name, username, discord_user_id) ASC"
        )
        return list(cursor.fetchall() or [])
    finally:
        cursor.close()


def set_bot_operator_active(user_id: str, is_active: bool) -> dict[str, Any] | None:
    if not _bot_operator_table_exists():
        return None

    cursor = get_dict_cursor()
    conn = get_conn()
    try:
        cursor.execute(
            "UPDATE bot_operator SET is_active = %s WHERE discord_user_id = %s "
            "RETURNING discord_user_id, username, global_name, avatar_url, scopes, is_active, last_login_at",
            (is_active, user_id),
        )
        record = cursor.fetchone()
        conn.commit()
        return record
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def set_bot_operator_scopes(user_id: str, scopes: list[str]) -> dict[str, Any] | None:
    if not _bot_operator_table_exists():
        return None

    cursor = get_dict_cursor()
    conn = get_conn()
    try:
        cursor.execute(
            "UPDATE bot_operator SET scopes = %s WHERE discord_user_id = %s "
            "RETURNING discord_user_id, username, global_name, avatar_url, scopes, is_active, last_login_at",
            (scopes, user_id),
        )
        record = cursor.fetchone()
        conn.commit()
        return record
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def upsert_bot_operator_login(
    *,
    user_id: str,
    username: str,
    global_name: str,
    avatar_url: str | None,
    scopes: list[str],
    last_login_at: datetime,
) -> None:
    if not _bot_operator_table_exists():
        return

    cursor = get_dict_cursor()
    conn = get_conn()
    try:
        cursor.execute(
            """
            INSERT INTO bot_operator (
                discord_user_id,
                username,
                global_name,
                avatar_url,
                scopes,
                is_active,
                last_login_at
            )
            VALUES (%s, %s, %s, %s, %s, true, %s)
            ON CONFLICT (discord_user_id)
            DO UPDATE SET
                username = EXCLUDED.username,
                global_name = EXCLUDED.global_name,
                avatar_url = EXCLUDED.avatar_url,
                scopes = EXCLUDED.scopes,
                last_login_at = EXCLUDED.last_login_at,
                is_active = true
            """,
            (user_id, username, global_name, avatar_url, scopes, last_login_at),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
