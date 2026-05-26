# Deployment Guide

This document is source of truth for deploying four OMO service surfaces: website, control room, bot API, bot worker.

## Service matrix

| Surface      | Status     | Source path     | Runtime entrypoint                                | Port | Domain                   |
| ------------ | ---------- | --------------- | ------------------------------------------------- | ---- | ------------------------ |
| Website      | Deployable | `website/`      | `waitress-serve --port 8880 website.app:app`      | 8880 | openmicodyssey.com       |
| Control Room | Deployable | `control_room/` | `waitress-serve --port 8480 control_room.app:app` | 8480 | admin.openmicodyssey.com |
| Bot API      | Deployable | `bot_api/`      | `waitress-serve --port 8787 bot_api.app:app`      | 8787 | api.openmicodyssey.com   |
| Bot Worker   | Deployable | `bot/`          | `python -m bot`                                   | none | internal                 |

## Infrastructure

All services run on a single Coolify server at `coolify.allucanget.biz` (internal IP `192.168.88.18`). Nginx Proxy Manager handles TLS termination and domain routing. PostgreSQL runs on `192.168.88.35`.

## Deployment steps

### 1. Website (openmicodyssey.com)

This service is public-site only. Do not expect editorial CMS routes or bot operator routes on this domain.

1. In Coolify, create new Application resource
2. Set base directory: `/` (repo root)
3. Build pack: Nixpacks
4. Start command: `waitress-serve --port 8880 website.app:app`
5. Port: `8880`
6. Health check: `GET /robots.txt`
7. Set environment variables (see `.env.website.example`)
8. In Nginx Proxy Manager, create proxy host: `openmicodyssey.com` → `http://192.168.88.18:8880`

### 2. Control Room (admin.openmicodyssey.com)

This service owns editorial login and CMS routes only. Use `/login`, `/`, and `/content/*` here. Bot/operator routes no longer live on this domain.

1. In Coolify, create new Application resource
2. Set base directory: `/` (repo root)
3. Build pack: Nixpacks
4. Start command: `waitress-serve --port 8480 control_room.app:app`
5. Port: `8480`
6. Health check: `GET /login`
7. Set environment variables (see `.env.control_room.example`)
8. In Nginx Proxy Manager, create proxy host: `admin.openmicodyssey.com` → `http://192.168.88.18:8480`

### 3. Bot API (api.openmicodyssey.com)

This service owns bot operator HTML routes under `/bot/*`, JSON APIs under `/bot/api/*`, Discord OAuth operator login, and top-level health at `/health`.

1. In Coolify, create new Application resource
2. Set base directory: `/` (repo root)
3. Build pack: Nixpacks
4. Start command: `waitress-serve --port 8787 bot_api.app:app`
5. Port: `8787`
6. Health check: `GET /health`
7. Set environment variables (see `.env.bot_api.example`)
8. In Nginx Proxy Manager, create proxy host: `api.openmicodyssey.com` → `http://192.168.88.18:8787`

### 4. Bot Worker (internal)

This service runs the Discord bot worker, including syndication polling, queue management, and mileage tracking.

1. In Coolify, create new Application or Worker resource
2. Set base directory: `/` (repo root)
3. Build pack: Nixpacks
4. Start command: `python -m bot`
5. No public port needed
6. Enable restart policy
7. Set environment variables (see bot worker section in ENVIRONMENT.md)

## Deployment checklist

- [ ] Generate `SECRET_KEY` for each service: `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Set `SITE_URL` to live canonical URL (no trailing slash)
- [ ] Confirm `DATABASE_URL` points to `192.168.88.35`
- [ ] Generate `ADMIN_PASSWORD_HASH` for control room only: `python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-password'))"`
- [ ] Set `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` on control room only, not website
- [ ] Set `OMO_BOT_API_URL` on control room so CMS links point at deployed bot API domain
- [ ] Configure Discord OAuth app in Discord Developer Portal for bot API operator login:
  - OAuth2 redirect URI: `https://api.openmicodyssey.com/oauth/discord/callback`
  - Environment variables on bot API: `OMO_DISCORD_CLIENT_ID`, `OMO_DISCORD_CLIENT_SECRET`, `OMO_DISCORD_REDIRECT_URI`
  - Requested scope: `identify`
  - Verify login with one allowed Discord user from `OMO_BOT_OPS_ALLOWED_USER_IDS`
- [ ] Verify website, control room, bot API domains respond correctly after deploy
- [ ] Verify website does not expose editorial or bot operator workflows
- [ ] Verify `admin.openmicodyssey.com` serves editorial login and `/content/*` only
- [ ] Verify `api.openmicodyssey.com` serves `/bot/*` and `/bot/api/*` operator workflows
- [ ] Verify bot worker connects to Discord and starts polling

## Detailed Coolify configs

See `deploy/` directory for per-service Coolify configuration files:

- `deploy/website-coolify.md`
- `deploy/control-room-coolify.md`
- `deploy/bot-api-coolify.md`
- `deploy/bot-worker-coolify.md`
