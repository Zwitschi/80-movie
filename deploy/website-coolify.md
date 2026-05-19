# Coolify Deployment Configuration

- Service: Website (openmicodyssey.com)
- Port: 8880

## Coolify Settings

- Resource type: Application
- Base directory: website/
- Build pack: Nixpacks
- Build command: (leave empty)
- Start command: gunicorn app:app --bind 0.0.0.0:8880 --workers 2
- Port: 8880
- Health check path: /robots.txt

## Environment Variables (set in Coolify)

```ini
SITE_URL=https://www.openmicodyssey.com
DATABASE_URL=postgresql://user:pass@192.168.88.35:5432/omo
SECRET_KEY=<generate-with-python-c-import-secrets-print-secrets.token-hex-32>
ADMIN_PASSWORD_HASH=<generate-with-python-c-from-werkzeug-security-import-generate-password-hash-print-generate-password-hash-your-password>
ADMIN_USERNAME=admin
CURRENT_YEAR=2026
MAPBOX_ACCESS_TOKEN=<optional>
```
