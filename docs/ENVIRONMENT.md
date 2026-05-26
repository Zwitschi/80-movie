# Environment Reference

This document is the source of truth for runtime environment variables actually read by the current codebase.

It covers service runtime config only. Historical or deploy-workflow-only values such as `WEBSITE_DEPLOY_*` and `HEROKU_API_KEY` are intentionally excluded.

## Example files

- Repo-root website example: `.env.website.example`
- Service-local website override example: `website/.env.example`
- Control room example: `.env.control_room.example`
- Bot API example: `.env.bot_api.example`
- Bot worker example: `.env.bot_worker.example`

## Website (`openmicodyssey.com`)

| Variable              | Default / fallback                         | Notes                                                                         |
| --------------------- | ------------------------------------------ | ----------------------------------------------------------------------------- |
| `SITE_URL`            | `https://www.openmicodyssey.com`           | Canonical URL, no trailing slash                                              |
| `DATABASE_URL`        | `postgresql://user:password@localhost/omo` | PostgreSQL DSN                                                                |
| `SECRET_KEY`          | `dev-secret-key-change-in-production`      | Flask session secret                                                          |
| `CURRENT_YEAR`        | current UTC year                           | Footer/context override                                                       |
| `MAPBOX_ACCESS_TOKEN` | empty                                      | Required only for hidden `/map` rendering                                     |
| `DATA_SOURCE`         | `DB`                                       | Config flag still exists, but current runtime content store is DB-backed only |

## Control Room (`admin.openmicodyssey.com`)

- `DATABASE_URL`: defaults to `postgresql://user:password@localhost/omo`; PostgreSQL DSN.
- `SECRET_KEY`: defaults to `dev-secret-key-change-in-production`; Flask session secret.
- `ADMIN_USERNAME`: defaults to `admin`; editorial login username.
- `ADMIN_PASSWORD`: defaults to empty; optional plain-text admin password for first-run seeding or hosts that mangle `$` in hash env values.
- `ADMIN_PASSWORD_HASH`: defaults to a generated Werkzeug hash for `admin`; preferred hashed admin credential and should be set explicitly in any real environment.
- `OMO_BOT_API_URL`: defaults to `https://api.openmicodyssey.com`; external link target for bot dashboard shortcuts in CMS templates.
- `CONTROL_ROOM_AUTO_CREATE`: defaults to `1`; waitress/module bootstrap flag, set to `0` only when you need to suppress module-level app creation.

## Bot API (`api.openmicodyssey.com`)

| Variable                           | Default / fallback                         | Notes                                                                                |
| ---------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------ |
| `OMO_DATABASE_URL`                 | falls back to `DATABASE_URL`               | Preferred PostgreSQL DSN input                                                       |
| `DATABASE_URL`                     | `postgresql://user:password@localhost/omo` | Used when `OMO_DATABASE_URL` is not set                                              |
| `SECRET_KEY`                       | `dev-secret-key-change-in-production`      | Flask session secret                                                                 |
| `OMO_DISCORD_CLIENT_ID`            | falls back to `DISCORD_CLIENT_ID`          | Discord OAuth client ID for operator login                                           |
| `OMO_DISCORD_CLIENT_SECRET`        | falls back to `DISCORD_CLIENT_SECRET`      | Discord OAuth client secret                                                          |
| `OMO_DISCORD_REDIRECT_URI`         | falls back to `DISCORD_REDIRECT_URI`       | Discord OAuth callback URL                                                           |
| `OMO_BOT_OPS_ALLOWED_USER_IDS`     | empty                                      | Comma-separated Discord user IDs allowed to log in before per-operator records exist |
| `OMO_BOT_OPS_DEFAULT_SCOPES`       | `ops.read`                                 | Comma-separated scopes granted on first login                                        |
| `OMO_BOT_OPS_SESSION_IDLE_MINUTES` | `60`                                       | Operator session idle timeout                                                        |
| `OMO_DISCORD_TOKEN`                | falls back to `DISCORD_TOKEN`              | Optional bot token surfaced in diagnostics and runtime-backed views                  |
| `OMO_DISCORD_GUILD_ID`             | unset                                      | Primary guild ID                                                                     |
| `OMO_SYNDICATION_SOURCES`          | empty                                      | Comma-separated sources; currently only `youtube` is supported                       |
| `OMO_SYNDICATION_POLL_SECONDS`     | `300`                                      | Syndication poll interval                                                            |
| `OMO_LOG_LEVEL`                    | `INFO`                                     | App and worker-adjacent diagnostics log level                                        |

### Operator scopes

| Scope               | Grants                                                 |
| ------------------- | ------------------------------------------------------ |
| `ops.read`          | Read-only access to bot status and operator dashboards |
| `ops.admin`         | All permissions (supersedes all other scopes)          |
| `queue.read`        | View queues and entries                                |
| `queue.write`       | Modify queues: clear, remove, and move entries         |
| `onboarding.read`   | View onboarding state and pending cleanups             |
| `onboarding.write`  | Reset onboarding and request role cleanup              |
| `mileage.read`      | View mileage ledger and user totals                    |
| `mileage.write`     | Adjust mileage and reverse mileage events              |
| `syndication.read`  | View syndication state                                 |
| `syndication.write` | Trigger syndication actions and config updates         |

## Bot Worker (internal)

| Variable                       | Default / fallback            | Notes                                                          |
| ------------------------------ | ----------------------------- | -------------------------------------------------------------- |
| `OMO_DISCORD_TOKEN`            | falls back to `DISCORD_TOKEN` | Required to start the worker                                   |
| `OMO_DATABASE_URL`             | falls back to `DATABASE_URL`  | Preferred PostgreSQL DSN                                       |
| `DATABASE_URL`                 | none                          | Fallback DSN when `OMO_DATABASE_URL` is not set                |
| `OMO_DISCORD_GUILD_ID`         | unset                         | Primary guild ID                                               |
| `OMO_DISCORD_CHANNEL_MAP`      | empty                         | Comma-separated `name:id` pairs                                |
| `OMO_SYNDICATION_SOURCES`      | empty                         | Comma-separated sources; currently only `youtube` is supported |
| `OMO_SYNDICATION_POLL_SECONDS` | `300`                         | Poll interval; must be a positive integer                      |
| `OMO_LOG_LEVEL`                | `INFO`                        | Runtime log level                                              |

## Local development loading order

- Website loads repo-root `.env` and then `website/.env`.
- Control room loads repo-root `.env` and then `website/.env`.
- Bot API loads repo-root `.env` and then `website/.env`.
- Bot worker loads process env, then repo-root `.env`, then `website/.env`.
- Prefer `OMO_*` names for bot-related settings.
- Legacy aliases still supported where noted: `DISCORD_TOKEN`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`.

## Minimum production sets

### Website

- `SITE_URL`
- `DATABASE_URL`
- `SECRET_KEY`

### Control Room

- `DATABASE_URL`
- `SECRET_KEY`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD_HASH`
- `OMO_BOT_API_URL`

### Bot API

- `OMO_DATABASE_URL` or `DATABASE_URL`
- `SECRET_KEY`
- `OMO_DISCORD_CLIENT_ID`
- `OMO_DISCORD_CLIENT_SECRET`
- `OMO_DISCORD_REDIRECT_URI`

Recommended for normal operator access control:

- `OMO_BOT_OPS_ALLOWED_USER_IDS`
- `OMO_BOT_OPS_DEFAULT_SCOPES`

Add these when the dashboard should reflect live bot runtime state:

- `OMO_DISCORD_TOKEN`
- `OMO_DISCORD_GUILD_ID`
- `OMO_SYNDICATION_SOURCES`
- `OMO_SYNDICATION_POLL_SECONDS`
- `OMO_LOG_LEVEL`

### Bot Worker

- `OMO_DISCORD_TOKEN`
- `OMO_DATABASE_URL` or `DATABASE_URL`

Add these when needed for live guild-specific behavior:

- `OMO_DISCORD_GUILD_ID`
- `OMO_DISCORD_CHANNEL_MAP`
- `OMO_SYNDICATION_SOURCES`
- `OMO_SYNDICATION_POLL_SECONDS`
- `OMO_LOG_LEVEL`
