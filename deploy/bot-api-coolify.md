# Coolify Deployment Configuration

- Service: Bot API (api.openmicodyssey.com)
- Port: 8787

Deploy this as its own Coolify application. This service owns the operator web UI and JSON API under `/bot/*` and `/bot/api/*`.

## Coolify Settings

- Resource type: Application
- Base directory: `/` (repo root, NOT bot_api/)
- Build pack: Nixpacks
- Build command: (leave empty)
- Start command: gunicorn bot_api.app:app --bind 0.0.0.0:8787 --workers 2
- Port: 8787
- Health check path: /health

> Keep the base directory at repo root so imports from `shared/` and `bot/` resolve correctly.

## Environment Variables (set in Coolify)

```ini
DATABASE_URL=postgresql://user:pass@192.168.88.35:5432/omo
SECRET_KEY=<generate-with-python-c-import-secrets-print-secrets.token-hex-32>
OMO_DISCORD_TOKEN=<discord-bot-token>
OMO_DISCORD_GUILD_ID=<discord-guild-id>
OMO_SYNDICATION_SOURCES=youtube
OMO_SYNDICATION_POLL_SECONDS=300
OMO_LOG_LEVEL=INFO
OMO_DISCORD_CLIENT_ID=<discord-oauth-app-client-id>
OMO_DISCORD_CLIENT_SECRET=<discord-oauth-app-client-secret>
OMO_DISCORD_REDIRECT_URI=https://api.openmicodyssey.com/oauth/discord/callback
OMO_BOT_OPS_ALLOWED_USER_IDS=<comma-separated-discord-user-ids>
OMO_BOT_OPS_DEFAULT_SCOPES=ops.read
```

## Verification

- Confirm `GET /health` returns a healthy response from the Coolify health check.
- Confirm `GET /bot/login` renders the operator login page.
- Confirm Discord OAuth redirects back to `https://api.openmicodyssey.com/oauth/discord/callback` successfully.
- Confirm `GET /bot/api/health` loads after operator login.
- Confirm the bot operator pages under `/bot/` render without template errors.
