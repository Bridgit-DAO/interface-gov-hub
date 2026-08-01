# OAuth redirect URIs (linked social accounts – not Web3Auth sign-in)

**Sign-in for Gov Hub uses [Web3Auth](https://web3auth.io/)** (`@web3auth/modal` on the client, `POST /api/auth/web3auth` in `routes/auth.py`). You configure **Web3Auth** in the [Web3Auth Dashboard](https://dashboard.web3auth.io/) (Client ID, allowed origins, etc.). That flow does **not** use the `/auth/<provider>/authorized` URLs below.

This document is only for the **optional Flask-Dance OAuth** feature that **links** Google, GitHub, Discord, or X to a profile after the user is already logged in (`routes/social_connect.py`: “OAuth social account linking”). Those routes are registered at `/auth/google`, `/auth/github`, `/auth/discord`, `/auth/twitter` in `app.py`. If you do **not** use linked accounts, you may not need these provider registrations at all.

---

Add these **exact** URLs to each provider's dashboard **for the linking feature**. The redirect URI must match character-for-character.

**Base URL:** `https://dev.hub.themetalayer.org` (or your production domain)

After DNS and nginx are live for **Gov Hub**, register the same paths on **`https://govhub.live`** (production) and **`https://dev.govhub.live`** (staging). Layer vanity hosts like `https://yourlayer.govhub.live` still use the same redirect paths (`/auth/.../authorized`) on that host only if you serve OAuth from those hostnames; typically you add **apex dev + prod** origins below.

### Gov Hub (`govhub.live` / `dev.govhub.live`)

| Provider | Redirect URI (production) | Redirect URI (dev) |
|----------|-------------------------|----------------------|
| **Google** | `https://govhub.live/auth/google/authorized` | `https://dev.govhub.live/auth/google/authorized` |
| **GitHub** | `https://govhub.live/auth/github/authorized` | `https://dev.govhub.live/auth/github/authorized` |
| **Discord** | `https://govhub.live/auth/discord/authorized` | `https://dev.govhub.live/auth/discord/authorized` |
| **Twitter/X** | `https://govhub.live/auth/twitter/authorized` | `https://dev.govhub.live/auth/twitter/authorized` |

**Google – Authorized JavaScript origins:** `https://govhub.live` and `https://dev.govhub.live`

## Redirect URIs (hub.themetalayer.org)

| Provider | Where to Add | Redirect URI (dev) | Redirect URI (prod) |
|----------|--------------|--------------------|---------------------|
| **Google** | [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → Your OAuth 2.0 Client → Authorized redirect URIs | `https://dev.hub.themetalayer.org/auth/google/authorized` | `https://hub.themetalayer.org/auth/google/authorized` |
| **GitHub** | [GitHub Developer Settings](https://github.com/settings/developers) → OAuth Apps → Your App → Authorization callback URL | `https://dev.hub.themetalayer.org/auth/github/authorized` | `https://hub.themetalayer.org/auth/github/authorized` |
| **Discord** | [Discord Developer Portal](https://discord.com/developers/applications) → Your App → OAuth2 → Redirects | `https://dev.hub.themetalayer.org/auth/discord/authorized` | `https://hub.themetalayer.org/auth/discord/authorized` |
| **Twitter/X** | [X Developer Portal](https://developer.x.com/) → Your App → User authentication settings → Callback URI | `https://dev.hub.themetalayer.org/auth/twitter/authorized` | `https://hub.themetalayer.org/auth/twitter/authorized` |

## Also Add (Authorized JavaScript Origins / Origins)

Some providers require the origin (without path):

- **Google:** Add `https://dev.hub.themetalayer.org` and `https://hub.themetalayer.org` to **Authorized JavaScript origins**
- **Discord:** Usually only needs the redirect URI above

---

## Discord: InvalidClientError (invalid_client)

**Cause:** You're using the **Public Key** instead of the **Client Secret**.

- **Public Key** (64 hex chars): Used for verifying Discord interactions/slash commands. Found under General Information.
- **Client Secret**: Used for OAuth2 token exchange. Found under OAuth2 → Client Information.

**Fix:**
1. Go to [Discord Developer Portal](https://discord.com/developers/applications) → Your App
2. Open **OAuth2** (not General Information)
3. Under **Client Information**, find **Client Secret**
4. Click **Reset Secret** if needed to reveal it (this invalidates the old one)
5. Copy the Client Secret and set `DISCORD_OAUTH_CLIENT_SECRET` in `.env`

---

## Twitter/X: 400 Bad Request on authorize

**Fixes to try:**
1. Go to [X Developer Portal](https://developer.x.com/) → Your App
2. Open **User authentication settings** (or Settings → User authentication)
3. Enable **OAuth 2.0** if not already
4. Set **App permissions** to at least Read (for `tweet.read`, `users.read`)
5. Add **Callback URI / Redirect URI**: `https://dev.hub.themetalayer.org/auth/twitter/authorized` (must match exactly)
6. Ensure app type is **Web App** (not Native) for confidential client
7. **Website URL**: Set to `https://dev.hub.themetalayer.org` when testing on dev – X may validate that redirect_uri matches the Website URL domain

## Debug logging

When OAuth fails, check `instance_dev/oauth_debug.log` (or `instance/oauth_debug.log` in production). It logs:
- Callback errors (when provider redirects back with `?error=...`)
- Token exchange failures (e.g. InvalidClientError)
- Full `request.args` and tracebacks

**Note:** If the 400 happens on X's authorize page *before* any redirect to your callback, the error never reaches your server. In that case, open the browser DevTools → Network tab, click the failed request to `x.com/i/.../oauth2/authorize`, and check the **Response** tab for X's error message.

---

## Production

For production OAuth on the Meta-Layer RFC site, also register URIs on `https://rfc.themetalayer.org` if you serve linked accounts there. Canonical Gov Hub production host is `https://hub.themetalayer.org` (see table above).
