# Web3Auth – Gov Hub

Gov Hub sign-in uses [Web3Auth Modal](https://web3auth.io/docs/sdk/web/modal) (`@web3auth/modal` in `templates/html_templates.py`, `POST /api/auth/web3auth` in `routes/auth.py`).

## Dashboard whitelist (required)

Each **origin** that runs Web3Auth must be registered manually in the [Web3Auth Dashboard](https://dashboard.web3auth.io/) for the estate `sapphire_devnet` client ID (`services/web3auth_config.py`).

**Canonical Gov Hub origins (whitelist these):**

| Environment | Origins / redirect URIs |
|-------------|-------------------------|
| Production | `https://hub.themetalayer.org` |
| Development | `https://dev.hub.themetalayer.org`, `https://dev.govhub.live` |
| Legacy | `https://govhub.live`, `https://rfc.themetalayer.org` (if still served) |

Optional local dev: `http://127.0.0.1:8001` (sapphire_devnet test client only).

## No dynamic whitelist API

Web3Auth does **not** expose an API or MCP to add redirect/origin URLs programmatically. Community threads confirm:

- Origins must be entered manually in the dashboard.
- Wildcard subdomains are **not** supported for whitelist entries.
- SDK `originData` does not register dashboard whitelist entries.

**Do not** whitelist every campaign vanity domain (`teilhardtest.com`, etc.). Use hub-canonical login instead (see below).

## Campaign vanity domains

Custom campaign hosts serve HTML from the same Gov Hub app but must **not** initialize Web3Auth on the vanity origin. Sign-in redirects to the hub with an absolute `?next=` return URL; after login, `/auth/campaign-handoff/` copies the session to the vanity host.

See `docs/CAMPAIGN_PAGES.md` (Sign-in on custom domains).

## Linked social accounts (not Web3Auth)

Optional Flask-Dance OAuth for linking Google/GitHub/Discord/X after sign-in uses separate redirect URIs. See `docs/OAUTH_REDIRECT_URIS.md`.

## Env overrides

| Variable | Purpose |
|----------|---------|
| `WEB3AUTH_CLIENT_ID_DEVNET` | Override shared devnet client ID |
| `WEB3AUTH_CLIENT_ID` | Paid mainnet client ID |
| `WEB3AUTH_USE_MAINNET` | `true` to use mainnet in production |
| `GOV_HUB_PUBLIC_URL` | Hub origin for campaign vanity login redirect (default dev/prod hub URLs) |
| `CAMPAIGN_HANDOFF_SECRET` | HMAC secret for vanity session handoff (defaults to `SECRET_KEY`) |

Never commit client secrets or `.env` values to git or Jau memories. The Web3Auth client ID is a public browser identifier.
