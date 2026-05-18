# Bot Worker

This folder contains the Discord bot worker scaffold and the current syndication polling seams.

## Run Locally

Preferred command from the repository root:

```powershell
.venv\Scripts\python.exe -m bot.omo_bot
```

Direct module entrypoint still works:

```powershell
.venv\Scripts\python.exe -m bot.omo_bot.main
```

The bot runtime reads env vars from this order when no explicit mapping is passed in code:

1. process environment
2. repo-root `.env`
3. `website/.env`

That means local bot runs can reuse the same `website/.env` file used by the Flask app, or a future repo-root `.env` if you split the worker config out later.

## Minimum local bot env

```dotenv
OMO_DISCORD_TOKEN=your-discord-bot-token
DATABASE_URL=postgresql://username:password@host:port/dbname
```

Recommended local additions:

```dotenv
OMO_DISCORD_GUILD_ID=123456789012345678
OMO_DISCORD_CHANNEL_MAP=queue:100,announcements:200
OMO_SYNDICATION_SOURCES=youtube
OMO_SYNDICATION_POLL_SECONDS=300
OMO_LOG_LEVEL=INFO
```

## Current behavior

- parses bot runtime config from env
- builds repository-backed or in-memory syndication state
- builds YouTube syndication adapter seam
- builds polling job and null delivery sink
- starts runtime lifecycle scaffold

Current runtime is still scaffold-level. It is useful for config validation, startup smoke checks, and exercising worker wiring, but it is not yet a feature-complete Discord automation service.

## OAuth note

Discord OAuth login for `/admin/bot` belongs to the Flask website, not this worker process. Those vars are read by the website app:

- `OMO_DISCORD_CLIENT_ID`
- `OMO_DISCORD_CLIENT_SECRET`
- `OMO_DISCORD_REDIRECT_URI`

Use `website/.env.example` and `docs/ENVIRONMENT.md` for the full combined matrix.
