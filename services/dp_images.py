"""Desirable Property artwork URLs (card / full / badge WebP).

Mirrors challenge-site ``src/lib/dp-images.ts``. Assets live under
``static/images/dps/`` by default; override with ``DP_IMAGES_BASE_URL``
(e.g. ``https://staging.desirableproperties.org/images/dps``).
"""
from __future__ import annotations

import os
import re
from typing import Literal, Optional

from services.groups import extract_dp_number
from services.workgroup_links import (
    extract_dp_number_from_title,
    is_dp_discovery_workgroup,
)

_DP_ID_RE = re.compile(r'^DP\s*0*(\d+)$', re.IGNORECASE)
_MAX_DP_NUM = 23

DpImageVariant = Literal['card', 'full', 'badge']

DP_DISCOVERY_CARD_IMAGE = 'dp-discovery.webp'
DP_DISCOVERY_FULL_IMAGE = 'dp-discovery.webp'
DP_DISCOVERY_BADGE_IMAGE = 'dp-discovery.webp'


def normalize_dp_number(dp_id: str | None) -> int | None:
    """Parse ``DP1`` / ``DP 01`` style ids; returns 1–23 or None."""
    if not dp_id:
        return None
    match = _DP_ID_RE.match(str(dp_id).strip())
    if not match:
        return None
    num = int(match.group(1))
    if 1 <= num <= _MAX_DP_NUM:
        return num
    return None


def dp_number_from_workgroup(workgroup) -> int | None:
    """Resolve DP number from acronym, slug, or display name."""
    for field in ('acronym', 'slug', 'name'):
        raw = getattr(workgroup, field, None) or ''
        num = extract_dp_number(str(raw))
        if num is not None:
            return num
        num = extract_dp_number_from_title(str(raw))
        if num is not None:
            return num
    return None


def dp_images_base_url() -> str:
    """Base path or absolute URL for DP artwork (no trailing slash)."""
    configured = (os.environ.get('DP_IMAGES_BASE_URL') or '').strip().rstrip('/')
    if configured:
        return configured
    return '/static/images/dps'


def dp_card_image_url(dp_num: int) -> str | None:
    if not (1 <= dp_num <= _MAX_DP_NUM):
        return None
    return f'{dp_images_base_url()}/card/DP{dp_num}.webp'


def dp_full_image_url(dp_num: int) -> str | None:
    if not (1 <= dp_num <= _MAX_DP_NUM):
        return None
    return f'{dp_images_base_url()}/full/DP{dp_num}.webp'


def dp_badge_image_url(dp_num: int) -> str | None:
    if not (1 <= dp_num <= _MAX_DP_NUM):
        return None
    return f'{dp_images_base_url()}/badge/dp{dp_num:02d}.webp'


def dp_discovery_image_url(variant: DpImageVariant = 'card') -> str:
    """Artwork for the shared DP Discovery meta-workgroup (not a numbered DP)."""
    if variant == 'full':
        filename = DP_DISCOVERY_FULL_IMAGE
        folder = 'full'
    elif variant == 'badge':
        filename = DP_DISCOVERY_BADGE_IMAGE
        folder = 'badge'
    else:
        filename = DP_DISCOVERY_CARD_IMAGE
        folder = 'card'
    return f'{dp_images_base_url()}/{folder}/{filename}'


def dp_image_url_for_number(dp_num: int, variant: DpImageVariant = 'card') -> str | None:
    if variant == 'full':
        return dp_full_image_url(dp_num)
    if variant == 'badge':
        return dp_badge_image_url(dp_num)
    return dp_card_image_url(dp_num)


def resolve_workgroup_image_url(
    workgroup,
    *,
    variant: DpImageVariant = 'card',
) -> str | None:
    """Card/badge/full URL for DP workgroups; stored image_url for others."""
    if is_dp_discovery_workgroup(workgroup):
        return dp_discovery_image_url(variant)
    dp_num = dp_number_from_workgroup(workgroup)
    if dp_num is not None:
        return dp_image_url_for_number(dp_num, variant)
    stored = (getattr(workgroup, 'image_url', None) or '').strip()
    return stored or None


def resolve_image_url_from_slug(
    slug: str,
    name: str = '',
    *,
    variant: DpImageVariant = 'card',
) -> str | None:
    """Resolve DP artwork from slug/name when only list-card fields are available."""
    from types import SimpleNamespace

    stub = SimpleNamespace(acronym=slug, slug=slug, name=name, image_url=None)
    return resolve_workgroup_image_url(stub, variant=variant)


def dp_image_alt(dp_num: int, name: str | None = None) -> str:
    dp_id = f'DP{dp_num}'
    label = f'{dp_id}: {name.strip()}' if name and name.strip() else dp_id
    return f'Illustration for Desirable Property {label}'
