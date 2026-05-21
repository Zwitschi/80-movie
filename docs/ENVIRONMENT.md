# Environment Reference

This document is the source of truth for runtime configuration across all OMO services.

## Website (openmicodyssey.com)

| Variable              | Required | Default                                         | Notes                            |
| --------------------- | -------- | ----------------------------------------------- | -------------------------------- |
| `SITE_URL`            | Yes      | `https://www.openmicodyssey.com`                | Canonical URL, no trailing slash |
| `DATABASE_URL`        | Yes      | `postgresql://user:pass@192.168.88.35:5432/omo` | PostgreSQL DSN                   |
| `SECRET_KEY`          | Yes      | `dev-secret-key-change-in-production`           | Flask session secret             |
| `CURRENT_YEAR`        | No       | current UTC year                                | Footer override                  |
| `MAPBOX_ACCESS_TOKEN` | No       | empty                                           | For hidden `/map` route          |
| `DATA_SOURCE`         | No       | `DB`                                            | Documented but DB-only in code   |

## Control Room (admin.openmicodyssey.com)

| Variable                           | Required      | Default                                         | Notes                                                                |
| ---------------------------------- | ------------- | ----------------------------------------------- | -------------------------------------------------------------------- |
| `DATABASE_URL`                     | Yes           | `postgresql://user:pass@192.168.88.35:5432/omo` | PostgreSQL DSN                                                       |
| `SECRET_KEY`                       | Yes           | `dev-secret-key-change-in-production`           | Flask session secret                                                 |
| `ADMIN_USERNAME`                   | No            | `admin`                                         | Editorial admin username                                             |
| `ADMIN_PASSWORD_HASH`              | Yes           | Werkzeug hash for `admin`                       | Editorial admin password                                             |
| `OMO_DISCORD_CLIENT_ID`            | Yes for OAuth | falls back to `DISCORD_CLIENT_ID`               | Discord OAuth client ID                                              |
| `OMO_DISCORD_CLIENT_SECRET`        | Yes for OAuth | falls back to `DISCORD_CLIENT_SECRET`           | Discord OAuth client secret                                          |
| `OMO_DISCORD_REDIRECT_URI`         | Yes for OAuth | falls back to `DISCORD_REDIRECT_URI`            | Callback URL                                                         |
| `OMO_BOT_OPS_ALLOWED_USER_IDS`     | No            | empty                                           | Comma-separated Discord user IDs allowed to log in                   |
| `OMO_BOT_OPS_DEFAULT_SCOPES`       | No            | `ops.read`                                      | Comma-separated scopes granted on first login (see scope list below) |
| `OMO_BOT_OPS_SESSION_IDLE_MINUTES` | No            | `60`                                            | Session idle timeout                                                 |

### Operator scopes

| Scope              | Grants                                                 |
| ------------------ | ------------------------------------------------------ |
| `ops.read`         | Read-only access to bot status and operator dashboards |
| `ops.admin`        | All permissions (supersedes all other scopes)          |
| `queue.read`       | View queues and entries                                |
| `queue.write`      | Modify queues: clear, remove/move entries              |
| `onboarding.read`  | View onboarding state and pending role cleanups        |
| `onboarding.write` | Reset onboarding, request role cleanup                 |
| `mileage.read`     | View mileage ledger and user totals                    |
| `mileage.write`    | Adjust mileage, reverse mileage events                 |

## Bot API (api.openmicodyssey.com)

| Variable                       | Required | Default                                         | Notes                          |
| ------------------------------ | -------- | ----------------------------------------------- | ------------------------------ |
| `DATABASE_URL`                 | Yes      | `postgresql://user:pass@192.168.88.35:5432/omo` | PostgreSQL DSN                 |
| `SECRET_KEY`                   | Yes      | `dev-secret-key-change-in-production`           | Flask session secret           |
| `OMO_DISCORD_TOKEN`            | No       | falls back to `DISCORD_TOKEN`                   | Discord bot token              |
| `OMO_DISCORD_GUILD_ID`         | No       | unset                                           | Primary guild ID (integer)     |
| `OMO_SYNDICATION_SOURCES`      | No       | empty                                           | Comma-separated (youtube only) |
| `OMO_SYNDICATION_POLL_SECONDS` | No       | `300`                                           | Poll interval                  |
| `OMO_LOG_LEVEL`                | No       | `INFO`                                          | Log level                      |

## Bot Worker (internal)

| Variable                       | Required | Default                                         | Notes                                         |
| ------------------------------ | -------- | ----------------------------------------------- | --------------------------------------------- |
| `OMO_DISCORD_TOKEN`            | Yes      | falls back to `DISCORD_TOKEN`                   | Discord bot token                             |
| `OMO_DATABASE_URL`             | Yes      | falls back to `DATABASE_URL`                    | PostgreSQL DSN; preferred over `DATABASE_URL` |
| `DATABASE_URL`                 | No       | `postgresql://user:pass@192.168.88.35:5432/omo` | Fallback DSN if `OMO_DATABASE_URL` not set    |
| `OMO_DISCORD_GUILD_ID`         | No       | unset                                           | Primary guild ID                              |
| `OMO_DISCORD_CHANNEL_MAP`      | No       | empty                                           | `name:id` pairs                               |
| `OMO_DISCORD_ROLE_MAP`         | No       | empty                                           | `name:id` pairs                               |
| `OMO_SYNDICATION_SOURCES`      | No       | empty                                           | Comma-separated sources                       |
| `OMO_SYNDICATION_POLL_SECONDS` | No       | `300`                                           | Poll interval                                 |
| `OMO_LOG_LEVEL`                | No       | `INFO`                                          | Log level                                     |

## Local development notes

- Website loads repo-root `.env` then `website/.env` via `shared/config.py` in `website/movie_site/__init__.py`
- Control room loads repo-root `.env` then `website/.env` via `shared/config.py`
- Bot API loads repo-root `.env` then `website/.env` via `shared/config.py`
- Bot worker loads process env → repo-root `.env` → `website/.env` via `bot/omo_bot/config.py`
- Prefer `OMO_*` prefixed names for clarity
- Legacy aliases: `DISCORD_TOKEN`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`

## Minimum production sets

### Website only

- `SITE_URL`, `DATABASE_URL`, `SECRET_KEY`

### Control Room only

- `DATABASE_URL`, `SECRET_KEY`, `ADMIN_PASSWORD_HASH`
- `OMO_DISCORD_CLIENT_ID`, `OMO_DISCORD_CLIENT_SECRET`, `OMO_DISCORD_REDIRECT_URI` (for operator login)

### Bot API

- `DATABASE_URL`, `SECRET_KEY`

### Bot Worker

- `OMO_DISCORD_TOKEN`, `OMO_DATABASE_URL` (or `DATABASE_URL`)
