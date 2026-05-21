# Coolify Deployment Configuration

- Service: Control Room (admin.openmicodyssey.com)
- Port: 8480

## Coolify Settings

- Resource type: Application
- Base directory: `/` (repo root, NOT control_room/)
- Build pack: Nixpacks
- Build command: (leave empty)
- Start command: gunicorn control_room.app:app --bind 0.0.0.0:8480 --workers 2
- Port: 8480
- Health check path: /admin/bot/api/health

## Environment Variables (set in Coolify)

```ini
DATABASE_URL=postgresql://user:pass@192.168.88.35:5432/omo
SECRET_KEY=<generate-with-python-c-import-secrets-print-secrets.token-hex-32>
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=<generate: python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-password'))">
OMO_DISCORD_CLIENT_ID=<discord-oauth-app-client-id>
OMO_DISCORD_CLIENT_SECRET=<discord-oauth-app-client-secret>
OMO_DISCORD_REDIRECT_URI=https://admin.openmicodyssey.com/oauth/discord/callback
OMO_BOT_OPS_ALLOWED_USER_IDS=<comma-separated-discord-user-ids>
OMO_BOT_OPS_DEFAULT_SCOPES=ops.read
OMO_BOT_OPS_SESSION_IDLE_MINUTES=60
```

> `ADMIN_USERNAME` / `ADMIN_PASSWORD_HASH` guard the editorial CMS login. For bot operator login use the Discord OAuth variables and `OMO_BOT_OPS_ALLOWED_USER_IDS`.
