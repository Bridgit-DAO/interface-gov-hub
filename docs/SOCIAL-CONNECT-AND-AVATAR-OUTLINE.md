# Social Account Connection & Avatar Size – Implementation Outline

**Status:** Phase 1 (Avatar) and Phase 2 (Connect) implemented. Install `flask-dance[sqla]` and set OAuth env vars to enable social linking.

## Overview

Two features:
1. **Connect Accounts** – OAuth-based linking of Google, GitHub, Twitter, LinkedIn, Discord, Reddit to user profiles (instead of manual URL fields).
2. **Avatar Size Fix** – Use provider-specific URL params to fetch larger profile images and avoid pixelation.

---

## Part 1: Connect Accounts (Flask-Dance)

### 1.1 Dependencies

```txt
# Add to requirements.txt (or equivalent)
flask-dance[sqla]>=7.0.0
```

`[sqla]` adds SQLAlchemy token storage for production.

### 1.2 Database Schema

**New model: `UserLinkedAccount`**

| Column        | Type        | Description                                      |
|---------------|-------------|--------------------------------------------------|
| `id`          | UUID        | Primary key                                      |
| `user_id`     | FK → user   | Owner                                            |
| `provider`    | String(50)  | `google`, `github`, `twitter`, `linkedin`, `discord`, `reddit` |
| `provider_user_id` | String(255) | Provider’s unique ID for the user         |
| `profile_url` | String(500) | Profile URL (e.g. https://github.com/username)   |
| `avatar_url`  | String(500) | Avatar URL (base, before size params)           |
| `display_name`| String(200) | Name from provider                              |
| `access_token`| Text        | OAuth access token (encrypted in prod)           |
| `token_expires_at` | DateTime | Optional expiry                         |
| `created_at`  | DateTime    | When linked                                     |

**Constraints:**
- `UNIQUE(user_id, provider)` – one link per provider per user
- `UNIQUE(provider, provider_user_id)` – one user per provider account

**Migration:** Add `user_linked_account` table and run migration.

### 1.3 OAuth Provider Setup (Developer Consoles)

| Provider  | Console / Docs | Notes |
|-----------|-----------------|-------|
| Google    | [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials | Redirect URI: `https://yourdomain.com/auth/google/authorized` |
| GitHub    | [GitHub Developer Settings](https://github.com/settings/developers) | OAuth App, callback: `/auth/github/authorized` |
| Twitter/X | [Twitter Developer Portal](https://developer.twitter.com/) | OAuth 2.0, callback: `/auth/twitter/authorized` |
| LinkedIn  | [LinkedIn Developers](https://www.linkedin.com/developers/) | OAuth 2.0, scopes: `r_liteprofile`, `r_emailaddress` (or newer equivalents) |
| Discord   | [Discord Developer Portal](https://discord.com/developers/applications) | OAuth2, redirect: `/auth/discord/authorized` |
| Reddit    | [Reddit Apps](https://www.reddit.com/prefs/apps) | OAuth 2.0, redirect: `/auth/reddit/authorized` |

### 1.4 Environment Variables

```env
# Google
GOOGLE_OAUTH_CLIENT_ID=xxx
GOOGLE_OAUTH_CLIENT_SECRET=xxx

# GitHub
GITHUB_OAUTH_CLIENT_ID=xxx
GITHUB_OAUTH_CLIENT_SECRET=xxx

# Twitter/X (OAuth 2.0)
TWITTER_OAUTH_CLIENT_ID=xxx
TWITTER_OAUTH_CLIENT_SECRET=xxx

# LinkedIn
LINKEDIN_OAUTH_CLIENT_ID=xxx
LINKEDIN_OAUTH_CLIENT_SECRET=xxx

# Discord
DISCORD_OAUTH_CLIENT_ID=xxx
DISCORD_OAUTH_CLIENT_SECRET=xxx

# Reddit
REDDIT_OAUTH_CLIENT_ID=xxx
REDDIT_OAUTH_CLIENT_SECRET=xxx
```

### 1.5 Routes & Blueprints

**New module: `routes/social_connect.py`**

| Route | Method | Auth | Description |
|-------|--------|------|-------------|
| `/auth/<provider>/` | GET | Yes | Start OAuth flow, redirect to provider |
| `/auth/<provider>/authorized` | GET | - | OAuth callback; create/update `UserLinkedAccount`, redirect to profile edit |
| `/auth/<provider>/disconnect` | POST | Yes | Remove link for provider |
| `/api/user/linked-accounts/` | GET | Yes | List linked accounts for current user |

**Flow:**
1. User on profile edit clicks “Connect Google” (or other provider).
2. Redirect to `/auth/google/` → Flask-Dance redirects to Google.
3. User authorizes → callback `/auth/google/authorized`.
4. Backend creates/updates `UserLinkedAccount`, stores token and profile data.
5. Redirect to `/profile/edit/` with success message.

### 1.6 Flask-Dance Blueprint Registration

```python
# In app.py or routes/social_connect.py
from flask_dance.contrib.google import make_google_blueprint
from flask_dance.contrib.github import make_github_blueprint
from flask_dance.contrib.twitter import make_twitter_blueprint
# ... etc.

# Use SQLAlchemy storage for tokens (production)
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage
from models import OAuth  # Token model for Flask-Dance

google_bp = make_google_blueprint(
    client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET"),
    storage=SQLAlchemyStorage(OAuth, db.session, user=current_user),
    redirect_to="profile_pages.profile_edit",
)
```

**Note:** Flask-Dance’s default flow is “login with provider.” For “connect to existing account,” you must:
- Require auth before `/auth/<provider>/` (redirect to login if not logged in).
- Pass `user_id` in OAuth `state` param; in the callback, verify state and create `UserLinkedAccount` for that user.
- Use a custom `redirect_url` that goes to profile edit, not the default login success page.
- Consider `flask_dance.consumer.oauth2.OAuth2ConsumerBlueprint` with a custom `authorized` handler that creates `UserLinkedAccount` instead of logging in.

### 1.7 Profile Edit UI Changes

**Replace “Social Links” card with “Connected Accounts”:**

- **Connected:** Show provider icon (larger, from provider or Font Awesome), display name, “Disconnect” button.
- **Not connected:** Show “Connect [Provider]” button.
- Use provider icons at 32×32 or 48×48 (or SVG) to avoid pixelation.
- Keep optional “Website” as a manual URL field (no OAuth).

**Icon sources:**
- Font Awesome: `fab fa-google`, `fab fa-github`, `fab fa-twitter`, `fab fa-linkedin`, `fab fa-discord`, `fab fa-reddit`
- Or official brand assets (SVG) from [Simple Icons](https://simpleicons.org/) or provider brand guidelines.

### 1.8 Data Stored Per Provider

```json
{
  "provider": "github",
  "provider_user_id": "12345",
  "profile_url": "https://github.com/username",
  "avatar_url": "https://avatars.githubusercontent.com/u/12345",
  "display_name": "Username"
}
```

`profile_url` → link on profile.  
`avatar_url` → base for avatar (apply size params in Part 2).

---

## Part 2: Avatar Size Fix

### 2.1 Provider-Specific URL Rewriting

**New utility: `services/avatar.py`**

```python
def avatar_url(url: str | None, size: int = 200) -> str | None:
    """
    Return avatar URL with provider-specific size params.
    size: desired pixel dimension (width/height).
    """
    if not url:
        return None
    # Google: lh3.googleusercontent.com, add ?sz=N or replace s96-c with s{N}-c
    # GitHub: avatars.githubusercontent.com, add ?s=N
    # Twitter: pbs.twimg.com, replace _normal with _400x400 or similar
    # Facebook: graph.facebook.com, add ?type=large or &width=N
    # Discord: cdn.discordapp.com - often already large
    # Reddit: styles.redditmedia.com - append ?width=N
    ...
```

### 2.2 URL Patterns by Provider

| Provider | URL pattern | Size param |
|----------|-------------|------------|
| **Google** | `lh3.googleusercontent.com`, `googleusercontent.com` | Add `?sz=400` or replace `s96-c` → `s400-c` |
| **GitHub** | `avatars.githubusercontent.com`, `avatars0.githubusercontent.com` | Add `?s=400` or `?size=400` |
| **Twitter/X** | `pbs.twimg.com`, `abs.twimg.com` | Replace `_normal` → `_400x400` or `_original` for best quality |
| **Facebook** | `graph.facebook.com`, `fbcdn.net` | Add `?type=large` or `&width=400` |
| **Discord** | `cdn.discordapp.com` | Often 128px; add `?size=256` if supported |
| **Reddit** | `styles.redditmedia.com`, `i.redd.it` | Add `?width=400` or similar |
| **LinkedIn** | `media.licdn.com` | Add size params per LinkedIn API |

### 2.3 Integration Points

**1. Web3Auth login (`routes/auth.py`):**
- When saving `profileImage` from Web3Auth, optionally rewrite URL before storing.
- Or store as-is and rewrite only when rendering.

**2. Avatar helper usage:**
- `services/avatar.py::avatar_url(url, size=200)` used everywhere avatars are shown.

**3. Call sites to update:**
- `routes/profile_pages.py` – profile view, profile edit
- `routes/directory.py` – People list
- `routes/admin.py` – nominee avatars
- `routes/guilds.py` – member avatars
- `templates/html_templates.py` – user menu / navbar avatar
- Any API returning `profileImage` (e.g. `routes/users.py`) – either rewrite in API or in frontend

**4. Preferred approach:**
- Add `get_avatar_url(user, size=200)` in `services/avatar.py` that:
  - Checks `user.profileImage` (Web3Auth)
  - Checks `UserLinkedAccount` for provider with best `avatar_url`
  - Applies `avatar_url()` rewriting
  - Falls back to default avatar

### 2.4 Display Sizes

| Context | Size | Notes |
|---------|------|-------|
| Profile header | 150–200px | Main profile image |
| Profile edit preview | 150px | Same as header |
| Directory / list | 36–48px | Thumbnails |
| Navbar / user menu | 32–40px | Small |
| Guild members | 32px | Small |

Use `object-fit: cover` and explicit `width`/`height` to avoid distortion.

---

## Implementation Order

### Phase 1: Avatar Size (smaller change)
1. Add `services/avatar.py` with `avatar_url()` and `get_avatar_url(user, size)`.
2. Update Web3Auth handler to store/rewrite URLs if desired.
3. Replace raw `user.profileImage` usage with `get_avatar_url(user, size)` at each call site.
4. Test with Google, GitHub, Twitter logins.

### Phase 2: Connect Accounts
1. Add `UserLinkedAccount` model and migration.
2. Add `OAuth` model for Flask-Dance token storage (if using SQLAlchemy storage).
3. Create `routes/social_connect.py` with Flask-Dance blueprints.
4. Register OAuth apps for each provider.
5. Add env vars and config.
6. Update profile edit UI: “Connected Accounts” section.
7. Add disconnect API and wire up buttons.
8. Optional: Use linked account avatars in `get_avatar_url()` when no Web3Auth image.

### Phase 3: Cleanup
1. Deprecate or repurpose `social_links` JSON (e.g. for manual “Website” only).
2. Add tests for `avatar_url()` and connect/disconnect flows.
3. Document OAuth app setup in `docs/` or `README`.

---

## File Checklist

| File | Action |
|------|--------|
| `models/identity.py` | Add `UserLinkedAccount` |
| `models/` (new or existing) | Add `OAuth` for Flask-Dance if using SQLAlchemy storage |
| `services/avatar.py` | **New** – `avatar_url()`, `get_avatar_url()` |
| `routes/social_connect.py` | **New** – OAuth connect/disconnect routes |
| `routes/auth.py` | Optionally rewrite `profileImage` on Web3Auth login |
| `routes/profile_pages.py` | Replace social links UI with connected accounts; use `get_avatar_url()` |
| `routes/users.py` | Use `get_avatar_url()` in API responses |
| `routes/directory.py` | Use `get_avatar_url()` |
| `routes/admin.py` | Use `get_avatar_url()` |
| `routes/guilds.py` | Use `get_avatar_url()` |
| `templates/html_templates.py` | Use `get_avatar_url()` for navbar |
| `migrations/` | Migration for `user_linked_account` (and `oauth` if needed) |
| `config.py` | Add OAuth-related config vars |
| `app.py` | Register social_connect blueprint |
| `requirements.txt` | Add `flask-dance[sqla]` |
| `.env.example` | Document OAuth env vars |

---

## Security Notes

- Store OAuth tokens encrypted at rest in production.
- Use HTTPS for all OAuth redirect URIs.
- Validate `state` in OAuth callbacks to prevent CSRF.
- Rate-limit connect/disconnect endpoints.
- On disconnect, revoke token with provider if supported.
