# Coolify Deployment Configuration

- Service: Control Room (admin.openmicodyssey.com)
- Port: 8480

Deploy this as the editorial CMS only. Bot operator tooling now lives on the separate Bot API service.

## Coolify Settings

- Resource type: Application
- Base directory: `/` (repo root, NOT control_room/)
- Build pack: Nixpacks
- Build command: (leave empty)
- Start command: waitress-serve --port 8480 control_room.app:app
- Port: 8480
- Health check path: /login

## Environment Variables (set in Coolify)

```ini
DATABASE_URL=postgresql://user:pass@192.168.88.35:5432/omo
SECRET_KEY=<generate-with-python-c-import-secrets-print-secrets.token-hex-32>
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=<generate: python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-password'))">
ADMIN_PASSWORD=<optional-seed-password-for-first-run>
OMO_BOT_API_URL=https://api.openmicodyssey.com
```

> `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` guard the editorial CMS login. `ADMIN_PASSWORD` is only needed if you want the app to seed the default admin user on startup. `OMO_BOT_API_URL` controls the external bot dashboard links in the CMS UI.

## Verification

- Confirm `GET /login` returns the editorial login page.
- Confirm authenticated editors can reach `/` and `/content/*` routes.
- Confirm the CMS navigation links out to `https://api.openmicodyssey.com` for bot operations.
