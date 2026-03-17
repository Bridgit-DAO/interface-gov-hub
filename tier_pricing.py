"""
International tier pricing by phone country — best practice for global communities.

This module provides country-based tier pricing for inscription services.
Communities can opt into offering tier pricing to provide equitable access
for participants from different economic regions.

Usage:
    from tier_pricing import get_tier_for_phone, get_inscribe_price
"""

from decimal import Decimal

# Country code prefix -> tier (1=full price, 2=30% off, 3=50% off)
# Lookup: try longest prefix first (e.g. "+880" before "+8")
PHONE_TIER_MAP = {
    "+1": 1, "+44": 1, "+49": 1, "+33": 1, "+81": 1, "+61": 1,
    "+65": 1, "+82": 1, "+41": 1, "+47": 1, "+46": 1, "+45": 1,
    "+55": 2, "+52": 2, "+54": 2, "+48": 2, "+420": 2, "+36": 2,
    "+40": 2, "+66": 2, "+60": 2, "+27": 2, "+90": 2, "+380": 2,
    "+91": 3, "+92": 3, "+880": 3, "+234": 3, "+254": 3,
    "+63": 3, "+84": 3, "+62": 3, "+20": 3, "+95": 3,
}

# Sorted by length descending for longest-prefix match
_TIER_PREFIXES = sorted(PHONE_TIER_MAP.keys(), key=lambda x: -len(x))


def get_tier_for_phone(phone: str) -> int:
    """
    Get tier (1, 2, or 3) for an E.164 phone number.
    Returns 1 (full price) if country not in map.
    """
    phone = (phone or "").strip()
    if not phone:
        return 1
    if not phone.startswith("+"):
        phone = "+" + phone.lstrip("0")
    for prefix in _TIER_PREFIXES:
        if phone.startswith(prefix):
            return PHONE_TIER_MAP[prefix]
    return 1


def get_inscribe_price(
    page_count: int,
    image_count: int,
    tier: int,
    price_per_page: float = 10.0,
    price_per_image: float = 5.0,
    tier2_discount_pct: int = 30,
    tier3_discount_pct: int = 50,
) -> dict:
    """
    Calculate inscription price with tier discount.

    Returns dict with: base_price_usd, discount_pct, final_price_usd, tier
    """
    base = Decimal(str(price_per_page)) * page_count + Decimal(str(price_per_image)) * image_count
    base = max(base, Decimal("1.00"))  # Minimum $1

    if tier == 1:
        discount_pct = 0
    elif tier == 2:
        discount_pct = tier2_discount_pct
    else:
        discount_pct = tier3_discount_pct

    discount_mult = Decimal("1") - Decimal(str(discount_pct)) / 100
    final = (base * discount_mult).quantize(Decimal("0.01"))

    return {
        "base_price_usd": float(base),
        "discount_pct": discount_pct,
        "final_price_usd": float(final),
        "tier": tier,
    }
