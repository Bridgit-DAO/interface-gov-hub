"""Avatar URL utilities: provider-specific size params to avoid pixelation."""
import re
from typing import Optional


def avatar_url(url: Optional[str], size: int = 200) -> Optional[str]:
    """
    Return avatar URL with provider-specific size params for higher resolution.
    size: desired pixel dimension (width/height).
    """
    if not url or not isinstance(url, str) or not url.strip():
        return None
    url = url.strip()
    size = max(48, min(size, 1500))

    # Google: lh3.googleusercontent.com, lh4, lh5, etc.
    if 'googleusercontent.com' in url:
        if 's96-c' in url or 's48-c' in url or 's64-c' in url:
            return re.sub(r's\d+-c', f's{size}-c', url)
        if 'photo.jpg' in url or 'photo.png' in url:
            sep = '&' if '?' in url else '?'
            return f"{url}{sep}sz={size}"
        return url

    # GitHub: avatars.githubusercontent.com, avatars0-3
    if 'githubusercontent.com' in url and '/u/' in url:
        sep = '&' if '?' in url else '?'
        return f"{url.rstrip('?')}{sep}s={size}"

    # Twitter/X: pbs.twimg.com, abs.twimg.com
    if 'twimg.com' in url:
        for suffix in ('_normal', '_mini', '_bigger', '_400x400'):
            if suffix in url:
                return url.replace(suffix, f'_{size}x{size}')
        if '_' not in url.split('/')[-1]:
            return url
        return url

    # Facebook: graph.facebook.com, fbcdn.net
    if 'facebook.com' in url or 'fbcdn.net' in url:
        sep = '&' if '?' in url else '?'
        if 'type=' not in url and 'width=' not in url:
            return f"{url}{sep}type=large"
        return url

    # Discord: cdn.discordapp.com
    if 'discord' in url and 'cdn' in url:
        sep = '&' if '?' in url else '?'
        return f"{url}{sep}size={size}"

    # Reddit: styles.redditmedia.com, i.redd.it
    if 'reddit' in url or 'redd.it' in url:
        sep = '&' if '?' in url else '?'
        return f"{url}{sep}width={size}"

    # LinkedIn: media.licdn.com
    if 'licdn.com' in url:
        return url

    return url


def is_user_uploaded_profile_image(url: Optional[str]) -> bool:
    """True when profileImage is a Gov Hub upload (not OAuth provider URL)."""
    return bool(url and str(url).strip().startswith('/uploads/profile_images/profile_'))


def get_avatar_url(user, size: int = 200, default: Optional[str] = None) -> str:
    """
    Get best available avatar URL for a user.
    Checks: profileImage (upload or Web3Auth), UserLinkedAccount avatars, then default.
    user: User model instance or dict (from get_current_user).
    """
    default = default or '/static/images/default-avatar.png'

    if not user:
        return default

    if isinstance(user, dict):
        user_id = user.get('id')
        if user_id:
            try:
                from models import User

                row = User.query.get(user_id)
                if row:
                    user = row
            except Exception:
                pass

    # 1. Web3Auth / uploaded profile image
    profile_image = getattr(user, 'profileImage', None)
    if profile_image:
        return avatar_url(profile_image, size) or default

    # 2. Linked accounts (prefer one with avatar)
    user_id = getattr(user, 'id', None)
    if user_id:
        try:
            from models import UserLinkedAccount

            linked = UserLinkedAccount.query.filter_by(user_id=user_id).order_by(
                UserLinkedAccount.created_at.desc()
            ).all()
            for acc in linked:
                if acc.avatar_url:
                    return avatar_url(acc.avatar_url, size) or default
        except Exception:
            pass

    return default
