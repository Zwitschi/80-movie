# Deployment Guide

This document is the source of truth for deploying the three OMO services: website, control room, and bot API.

## Service matrix

| Surface      | Status     | Source path     | Runtime entrypoint                                 | Port | Domain                   |
| ------------ | ---------- | --------------- | -------------------------------------------------- | ---- | ------------------------ |
| Website      | Deployable | `website/`      | `gunicorn app:app --bind 0.0.0.0:8880 --workers 2` | 8880 | openmicodyssey.com       |
| Control Room | Deployable | `control_room/` | `gunicorn app:app --bind 0.0.0.0:8480 --workers 2` | 8480 | admin.openmicodyssey.com |
| Bot API      | Deployable | `bot_api/`      | `gunicorn app:app --bind 0.0.0.0:8787 --workers 2` | 8787 | api.openmicodyssey.com   |
| Bot Worker   | Scaffold   | `bot/omo_bot/`  | `python -m bot.omo_bot`                            | none | internal                 |

## Infrastructure

All services run on a single Coolify server at `coolify.allucanget.biz` (internal IP `192.168.88.18`). Nginx Proxy Manager handles TLS termination and domain routing. PostgreSQL runs on `192.168.88.35`.

## Deployment steps

### 1. Website (openmicodyssey.com)

This service is public-site only. Do not expect editorial CMS routes or bot operator routes on this domain.

1. In Coolify, create new Application resource
2. Set base directory: `/` (repo root)
3. Build pack: Nixpacks
4. Start command: `gunicorn website.app:app --bind 0.0.0.0:8880 --workers 2`
5. Port: `8880`
6. Health check: `GET /robots.txt`
7. Set environment variables (see `.env.website.example`)
8. In Nginx Proxy Manager, create proxy host: `openmicodyssey.com` → `http://192.168.88.18:8880`

### 2. Control Room (admin.openmicodyssey.com)

This service owns both editorial CMS routes under `/admin` and bot/operator routes under `/admin/bot`.

1. In Coolify, create new Application resource
2. Set base directory: `/` (repo root)
3. Build pack: Nixpacks
4. Start command: `gunicorn control_room.app:app --bind 0.0.0.0:8480 --workers 2`
5. Port: `8480`
6. Health check: `GET /admin/bot/api/health`
7. Set environment variables (see `.env.control_room.example`)
8. In Nginx Proxy Manager, create proxy host: `admin.openmicodyssey.com` → `http://192.168.88.18:8480`

### 3. Bot API (api.openmicodyssey.com)

1. In Coolify, create new Application resource
2. Set base directory: `/` (repo root)
3. Build pack: Nixpacks
4. Start command: `gunicorn bot_api.app:app --bind 0.0.0.0:8787 --workers 2`
5. Port: `8787`
6. Health check: `GET /health`
7. Set environment variables (see `.env.bot_api.example`)
8. In Nginx Proxy Manager, create proxy host: `api.openmicodyssey.com` → `http://192.168.88.18:8787`

### 4. Bot Worker (internal)

1. In Coolify, create new Application or Worker resource
2. Set base directory: `/` (repo root)
3. Start command: `python -m bot.omo_bot`
4. No public port needed
5. Enable restart policy
6. Set environment variables (see bot worker section in ENVIRONMENT.md)

## Deployment checklist

- [ ] Generate `SECRET_KEY` for each service: `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Set `SITE_URL` to live canonical URL (no trailing slash)
- [ ] Confirm `DATABASE_URL` points to `192.168.88.35`
- [ ] Generate `ADMIN_PASSWORD_HASH` for control room only: `python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-password'))"`
- [ ] Set `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` on control room only, not website
- [ ] Configure Discord OAuth app in the Discord Developer Portal for control room operator login:
  - OAuth2 redirect URI: `https://admin.openmicodyssey.com/oauth/discord/callback`
  - Environment variables on control room: `OMO_DISCORD_CLIENT_ID`, `OMO_DISCORD_CLIENT_SECRET`, `OMO_DISCORD_REDIRECT_URI`
  - Requested scope: `identify`
  - Verify login with one allowed Discord user from `OMO_BOT_OPS_ALLOWED_USER_IDS`
- [ ] Verify all 3 domains respond correctly after deploy
- [ ] Verify website does not expose `/admin` or `/admin/bot`; use `admin.openmicodyssey.com` for all editorial and operator workflows
- [ ] Verify bot worker connects to Discord and starts polling

## Detailed Coolify configs

See `deploy/` directory for per-service Coolify configuration files:

- `deploy/website-coolify.md`
- `deploy/control-room-coolify.md`
- `deploy/bot-api-coolify.md`
- `deploy/bot-worker-coolify.md`
