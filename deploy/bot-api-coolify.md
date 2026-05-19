# Coolify Deployment Configuration

- Service: Bot API (api.openmicodyssey.com)
- Port: 8787

## Coolify Settings

- Resource type: Application
- Base directory: `/` (repo root, NOT bot_api/)
- Build pack: Nixpacks
- Build command: (leave empty)
- Start command: gunicorn bot_api.app:app --bind 0.0.0.0:8787 --workers 2
- Port: 8787
- Health check path: /health

## Environment Variables (set in Coolify)

```ini
DATABASE_URL=postgresql://user:pass@192.168.88.35:5432/omo
SECRET_KEY=<generate-with-python-c-import-secrets-print-secrets.token-hex-32>
OMO_DISCORD_TOKEN=<discord-bot-token>
OMO_DISCORD_GUILD_ID=<discord-guild-id>
OMO_SYNDICATION_SOURCES=youtube
OMO_SYNDICATION_POLL_SECONDS=300
OMO_LOG_LEVEL=INFO
```
