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

    import uuid
    try:
        uuid.UUID(user_id)
    except (ValueError, TypeError):
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


def create_user_with_password_hash(username: str, email: str, password_hash: str) -> dict[str, Any] | None:
    if not _users_table_exists():
        return None

    cursor = get_dict_cursor()
    conn = get_conn()
    try:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) "
            "VALUES (%s, %s, %s) "
            "RETURNING id, username, email, is_active, created_at",
            (username, email, password_hash),
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


def seed_default_admin(
    config_username: str,
    config_password: str | None = None,
    config_password_hash: str | None = None,
) -> dict[str, Any] | None:
    if user_exists():
        return None

    user = None
    if config_password:
        user = create_user(
            config_username, f"{config_username}@localhost", config_password)
    elif config_password_hash:
        user = create_user_with_password_hash(
            config_username,
            f"{config_username}@localhost",
            config_password_hash,
        )

    if user:
        assign_role(user['id'], 'admin')
    return user


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return check_password_hash(stored_hash, password)
    except (TypeError, ValueError):
        return False


def list_users() -> list[dict[str, Any]]:
    """Return all users with their roles."""
    if not _users_table_exists():
        return []

    cursor = get_dict_cursor()
    try:
        cursor.execute(
            "SELECT id, username, email, is_active, created_at, updated_at "
            "FROM users ORDER BY created_at DESC"
        )
        users = cursor.fetchall() or []
        for user in users:
            user['roles'] = list_user_roles(user['id'])
        return users
    finally:
        cursor.close()


def update_user(
    user_id: str,
    username: str | None = None,
    email: str | None = None,
    is_active: bool | None = None,
) -> dict[str, Any] | None:
    """Update user fields. Returns updated user or None."""
    if not _users_table_exists():
        return None

    fields = []
    params = []
    if username is not None:
        fields.append("username = %s")
        params.append(username)
    if email is not None:
        fields.append("email = %s")
        params.append(email)
    if is_active is not None:
        fields.append("is_active = %s")
        params.append(is_active)

    if not fields:
        return get_user_by_id(user_id)

    fields.append("updated_at = now()")
    params.append(user_id)

    cursor = get_dict_cursor()
    conn = get_conn()
    try:
        cursor.execute(
            f"UPDATE users SET {', '.join(fields)} WHERE id = %s "
            "RETURNING id, username, email, is_active, created_at, updated_at",
            params,
        )
        record = cursor.fetchone()
        conn.commit()
        return record
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def delete_user(user_id: str) -> bool:
    """Delete a user by ID. Returns True if deleted."""
    if not _users_table_exists():
        return False

    cursor = get_dict_cursor()
    conn = get_conn()
    try:
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def update_password(user_id: str, new_password: str) -> bool:
    """Update a user's password. Returns True on success."""
    if not _users_table_exists():
        return False

    cursor = get_dict_cursor()
    conn = get_conn()
    try:
        cursor.execute(
            "UPDATE users SET password_hash = %s, updated_at = now() WHERE id = %s",
            (generate_password_hash(new_password), user_id),
        )
        updated = cursor.rowcount > 0
        conn.commit()
        return updated
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
