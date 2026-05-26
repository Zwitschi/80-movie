# Coolify Deployment Configuration

- Service: Website (openmicodyssey.com)
- Port: 8880

## Coolify Settings

- Resource type: Application
- Base directory: `/` (repo root, NOT website/)
- Build pack: Nixpacks
- Build command: (leave empty)
- Start command: waitress-serve --port 8880 website.app:app
- Port: 8880
- Health check path: /robots.txt

## Environment Variables (set in Coolify)

```ini
SITE_URL=https://www.openmicodyssey.com
DATABASE_URL=postgresql://user:pass@192.168.88.35:5432/omo
SECRET_KEY=<generate-with-python-c-import-secrets-print-secrets.token-hex-32>
CURRENT_YEAR=2026
MAPBOX_ACCESS_TOKEN=<optional>
```

> `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` are control room variables — do not set them on the website service.
