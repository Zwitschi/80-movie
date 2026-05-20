# Coolify Deployment Configuration

- Service: Bot Worker (internal)
- Port: none

## Coolify Settings

- Resource type: Worker or Application
- Base directory: `/` (repo root)
- Build pack: Nixpacks
- Build command: (leave empty)
- Start command: `python -m bot.omo_bot`
- No public port needed
- Restart policy: enabled
- Health signal: process stays alive; validate startup logs for Discord auth and polling loop

## Environment Variables (set in Coolify)

```ini
DATABASE_URL=postgresql://user:pass@192.168.88.35:5432/omo
OMO_DISCORD_TOKEN=<discord-bot-token>
OMO_DISCORD_GUILD_ID=<discord-guild-id>
OMO_SYNDICATION_SOURCES=youtube
OMO_SYNDICATION_POLL_SECONDS=300
OMO_LOG_LEVEL=INFO
```

## Verification

- Confirm the worker process stays running after deploy
- Confirm startup logs show Discord REST auth success
- Confirm startup logs show the first syndication poll completes
- Confirm control room health views reflect the worker as healthy
