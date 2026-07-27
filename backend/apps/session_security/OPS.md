# Session Security / GeoIP operations notes

## Overview

Login requires IP capture and IP-derived geolocation when
`ip_location_enforcement_enabled` is true (default). Location is **not**
browser GPS — it comes from the server GeoIP provider (ip-api / MaxMind).
Chrome "Location" permission for the site is unrelated.

**Golden rule:** every audit row’s Location describes the **same IP** stored on
that row. Session geo is never reused with a different request IP.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GEOIP_PROVIDER` | `http` | `http` (ip-api.com + cache), `memory` (tests), or `maxmind` |
| `GEOIP_HTTP_TIMEOUT_SECONDS` | `1.5` | HTTP geo request timeout |
| `GEOIP_CACHE_TTL_SECONDS` | `604800` (7d) | Cache TTL per IP (avoids repeat HTTP) |
| `GEOIP_DB_PATH` | `<BASE_DIR>/data/GeoLite2-City.mmdb` | Path for MaxMind only |
| `TRUST_X_FORWARDED_FOR` | `true` | Prefer `X-Real-IP`, else rightmost public `X-Forwarded-For` hop |

## Client IP (behind nginx)

Production nginx sets:

- `X-Real-IP: $remote_addr` (authoritative)
- `X-Forwarded-For: $proxy_add_x_forwarded_for`

The app prefers **X-Real-IP**, then the **rightmost public** XFF entry (the hop
nginx appends). Left-most XFF is not trusted (client-spoofable).

## Browser geolocation (login)

On `/login` mount the SPA requests `navigator.geolocation` (native browser
prompt). Allow → lat/lng/accuracy stored in audit `metadata.browser_geo`.
Deny / timeout → login continues; `location_resolution=ip_fallback` and
`location` remains server IP GeoIP.

Device facts (browser, OS, screen, timezone, language) are sent as
`client_context.device` and shown on Login activity (`/profile/login-activity`).

**Never trust client-claimed IP.** Server still resolves IP via X-Real-IP / XFF.

## Activity network capture

`SessionSecurityRequestContextMiddleware` stores client IP/UA for the request.
Money (passbook) and admin activity events attach that IP + GeoIP when the
write happens inside an HTTP request. Webhooks / async jobs without a client
request store `network_capture=unavailable` and location `N/A (server-side)`.

Auth lookups (login/refresh) still call GeoIP directly. Money/admin resolve geo
lazily only when recording (cached).

## Recommended production

```bash
GEOIP_PROVIDER=http
GEOIP_HTTP_TIMEOUT_SECONDS=1.5
GEOIP_CACHE_TTL_SECONDS=604800
TRUST_X_FORWARDED_FOR=true
```

ip-api.com free tier is rate-limited (~45 req/min); caching keeps us under that.

## Optional MaxMind

1. Download GeoLite2-City `.mmdb`
2. Set `GEOIP_PROVIDER=maxmind` and `GEOIP_DB_PATH=...`
3. Restart backend

## Admin UI

- Users page → **Settings** → `/admin/user-management-settings`
- Per-user Activity tab on user profile + self Profile & Settings
- Login activity page: `/profile/login-activity`
- Location: browser GPS when allowed, else IP GeoIP

## Deploy checklist

1. `pip install -r requirements.txt` (includes `openpyxl`, `geoip2`, `requests`)
2. `python manage.py migrate`
3. Confirm `GEOIP_PROVIDER=http` (or maxmind)
4. Frontend build + restart processes
5. Smoke: login with public IP → audit shows real city for **that** IP
6. Smoke: pay-in via API → money row has same client IP/location as the request
