# Environment Reference

This document is the source of truth for runtime configuration across the Flask website, the embedded bot control room, and the planned Discord bot worker.

## Website runtime

| Variable              | Required           | Default                                    | Used by               | Notes                                                                                                                                                                   |
| --------------------- | ------------------ | ------------------------------------------ | --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SITE_URL`            | Yes for production | `https://www.openmicodyssey.com`           | website               | Canonical public base URL used for schema, sitemap, and metadata generation. Use no trailing slash in production.                                                       |
| `DATABASE_URL`        | Yes                | `postgresql://user:password@localhost/omo` | website, bot fallback | PostgreSQL DSN used by the website content store and DB helpers. The bot can also fall back to this when `OMO_DATABASE_URL` is unset.                                   |
| `SECRET_KEY`          | Yes for production | `dev-secret-key-change-in-production`      | website               | Flask session secret for the public site, admin login, and embedded control room. Never use the default outside local development.                                      |
| `ADMIN_USERNAME`      | No                 | `admin`                                    | website admin         | Username for the editorial admin login.                                                                                                                                 |
| `ADMIN_PASSWORD_HASH` | Yes for production | generated hash for `admin`                 | website admin         | Werkzeug password hash for the editorial admin login.                                                                                                                   |
| `CURRENT_YEAR`        | No                 | current UTC year                           | website               | Footer and template year override.                                                                                                                                      |
| `MAPBOX_ACCESS_TOKEN` | Optional           | empty                                      | website               | Public Mapbox token for the hidden `/map` route. Required only if that route is used.                                                                                   |
| `DATA_SOURCE`         | No                 | `DB`                                       | website config        | Present in config and health output, but the current runtime content-store factory is DB-backed only. Treat JSON mode as documented intent, not an active runtime path. |

## Control-room operator auth

These values configure the embedded `/admin/bot` operator login flow inside the Flask app.

| Variable                           | Required           | Default                               | Used by      | Notes                                                                                   |
| ---------------------------------- | ------------------ | ------------------------------------- | ------------ | --------------------------------------------------------------------------------------- |
| `OMO_DISCORD_CLIENT_ID`            | Yes for real OAuth | falls back to `DISCORD_CLIENT_ID`     | control room | Discord OAuth client id for operator login.                                             |
| `OMO_DISCORD_CLIENT_SECRET`        | Yes for real OAuth | falls back to `DISCORD_CLIENT_SECRET` | control room | Discord OAuth client secret for operator login.                                         |
| `OMO_DISCORD_REDIRECT_URI`         | Yes for real OAuth | falls back to `DISCORD_REDIRECT_URI`  | control room | Full callback URL for `/admin/bot/oauth/callback`.                                      |
| `OMO_BOT_OPS_ALLOWED_USER_IDS`     | Optional           | empty                                 | control room | Comma-separated fallback allowlist used when no DB-backed `bot_operator` record exists. |
| `OMO_BOT_OPS_DEFAULT_SCOPES`       | Optional           | `ops.read`                            | control room | Comma-separated fallback scope list for allowlisted operators without DB-backed scopes. |
| `OMO_BOT_OPS_SESSION_IDLE_MINUTES` | Optional           | `60`                                  | control room | Idle timeout for operator sessions.                                                     |

## Discord bot worker

These values are parsed by `bot/omo_bot/config.py` for the planned bot runtime.

| Variable                       | Required | Default                       | Used by | Notes                                                                                            |
| ------------------------------ | -------- | ----------------------------- | ------- | ------------------------------------------------------------------------------------------------ |
| `OMO_DISCORD_TOKEN`            | Yes      | falls back to `DISCORD_TOKEN` | bot     | Discord bot token. Required to start the worker.                                                 |
| `OMO_DISCORD_GUILD_ID`         | Optional | unset                         | bot     | Primary guild id for bot operations. Must be an integer when set.                                |
| `OMO_DISCORD_CHANNEL_MAP`      | Optional | empty                         | bot     | Comma-separated `name:id` pairs such as `queue:100,announcements:200`.                           |
| `OMO_DATABASE_URL`             | Optional | falls back to `DATABASE_URL`  | bot     | Dedicated DB DSN for the bot if it should not share the website DSN directly.                    |
| `OMO_SYNDICATION_SOURCES`      | Optional | empty                         | bot     | Comma-separated source list for syndication polling. Current MVP runtime accepts `youtube` only. |
| `OMO_SYNDICATION_POLL_SECONDS` | Optional | `300`                         | bot     | Poll interval for syndication jobs. Must be a positive integer.                                  |
| `OMO_LOG_LEVEL`                | Optional | `INFO`                        | bot     | Log level, normalized to uppercase.                                                              |

## Local development notes

- The website loads `website/.env` automatically through `python-dotenv` in `website/movie_site/config.py`.
- `website/.env.example` currently covers only a subset of the full runtime surface and still includes some legacy deployment placeholders. Use this page as the authoritative matrix when adding or reviewing configuration.
- The embedded control room and the planned bot share some Discord-related env names through fallback aliases. Prefer the `OMO_*` names when configuring repo-owned services so the intent stays explicit.

## Minimum production sets

### Website only

- `SITE_URL`
- `DATABASE_URL`
- `SECRET_KEY`
- `ADMIN_PASSWORD_HASH`

### Website plus embedded control room

- Website-only set
- `OMO_DISCORD_CLIENT_ID`
- `OMO_DISCORD_CLIENT_SECRET`
- `OMO_DISCORD_REDIRECT_URI`

### Bot worker

- `OMO_DISCORD_TOKEN`
- `DATABASE_URL` or `OMO_DATABASE_URL`
