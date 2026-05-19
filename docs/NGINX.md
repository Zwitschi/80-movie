# Nginx Proxy Manager Configuration

Nginx Proxy Manager (NPM) is pre-configured on the Coolify server. No project-level Nginx config files are needed.

## Proxy Hosts

| Domain                     | Forward IP      | Forward Port | SSL           | Notes                         |
| -------------------------- | --------------- | ------------ | ------------- | ----------------------------- |
| `openmicodyssey.com`       | `192.168.88.18` | `8880`       | Let's Encrypt | Website                       |
| `www.openmicodyssey.com`   | `192.168.88.18` | `8880`       | Let's Encrypt | Website (redirect to non-www) |
| `admin.openmicodyssey.com` | `192.168.88.18` | `8480`       | Let's Encrypt | Control Room                  |
| `api.openmicodyssey.com`   | `192.168.88.18` | `8787`       | Let's Encrypt | Bot API                       |

## Cloudflare DNS Records

| Type  | Name    | Content              | Proxy   |
| ----- | ------- | -------------------- | ------- |
| A     | `@`     | Coolify server IP    | Proxied |
| CNAME | `www`   | `openmicodyssey.com` | Proxied |
| CNAME | `admin` | Coolify server IP    | Proxied |
| CNAME | `api`   | Coolify server IP    | Proxied |

## NPM Settings per Proxy Host

- **Scheme**: http
- **Forward Hostname/IP**: `192.168.88.18`
- **Forward Port**: service-specific (8880/8480/8787)
- **Cache Assets**: enabled
- **Block Common Exploits**: enabled
- **Websockets Support**: enabled (for control room)
- **SSL**: Let's Encrypt, Force SSL, HTTP/2 support
