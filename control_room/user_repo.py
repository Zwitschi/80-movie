from __future__ import annotations

from typing import Any
from werkzeug.security import generate_password_hash, check_password_hash

from shared.db import get_conn, get_dict_cursor


def _users_table_exists() -> bool:
    cursor = get_dict_cursor()
    try:
        cursor.execute("SELECT to_regclass('public.users') AS table_name")
        row = cursor.fetchone()
        return bool(row and row.get('table_name'))
    finally:
        cursor.close()


def get_user_by_username(username: str) -> dict[str, Any] | None:
    if not _users_table_exists():
        return None

    cursor = get_dict_cursor()
    try:
        cursor.execute(
            "SELECT id, username, email, password_hash, is_active, created_at "
            "FROM users WHERE username = %s",
            (username,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    if not _users_table_exists():
        return None

    cursor = get_dict_cursor()
    try:
        cursor.execute(
            "SELECT id, username, email, password_hash, is_active, created_at "
            "FROM users WHERE id = %s",
            (user_id,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()


def list_user_roles(user_id: str) -> list[str]:
    if not _users_table_exists():
        return []

    cursor = get_dict_cursor()
    try:
        cursor.execute(
            "SELECT r.name FROM roles r "
            "JOIN user_roles ur ON ur.role_id = r.id "
            "WHERE ur.user_id = %s",
            (user_id,),
        )
        return [row['name'] for row in (cursor.fetchall() or [])]
    finally:
        cursor.close()


def create_user(username: str, email: str, password: str) -> dict[str, Any] | None:
    if not _users_table_exists():
        return None

    cursor = get_dict_cursor()
    conn = get_conn()
    try:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) "
            "VALUES (%s, %s, %s) "
            "RETURNING id, username, email, is_active, created_at",
            (username, email, generate_password_hash(password)),
        )
        record = cursor.fetchone()
        conn.commit()
        return record
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def assign_role(user_id: str, role_name: str) -> bool:
    if not _users_table_exists():
        return False

    cursor = get_dict_cursor()
    conn = get_conn()
    try:
        cursor.execute(
            "SELECT id FROM roles WHERE name = %s",
            (role_name,),
        )
        role = cursor.fetchone()
        if not role:
            return False

        cursor.execute(
            "INSERT INTO user_roles (user_id, role_id) "
            "VALUES (%s, %s) "
            "ON CONFLICT (user_id, role_id) DO NOTHING",
            (user_id, role['id']),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def create_role(name: str, permissions: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not _users_table_exists():
        return None

    import json
    cursor = get_dict_cursor()
    conn = get_conn()
    try:
        cursor.execute(
            "INSERT INTO roles (name, permissions) "
            "VALUES (%s, %s) "
            "RETURNING id, name, permissions, created_at",
            (name, json.dumps(permissions or {})),
        )
        record = cursor.fetchone()
        conn.commit()
        return record
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def user_exists() -> bool:
    if not _users_table_exists():
        return False

    cursor = get_dict_cursor()
    try:
        cursor.execute("SELECT 1 FROM users LIMIT 1")
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def seed_default_admin(config_username: str, config_password: str) -> dict[str, Any] | None:
    if user_exists():
        return None

    user = create_user(
        config_username, f"{config_username}@localhost", config_password)
    if user:
        assign_role(user['id'], 'admin')
    return user


def verify_password(stored_hash: str, password: str) -> bool:
    return check_password_hash(stored_hash, password)
