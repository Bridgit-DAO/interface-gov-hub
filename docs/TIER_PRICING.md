# International Tier Pricing — Best Practice for Overweb Communities

Tier pricing by phone country provides equitable access to inscription and other paid services for participants from different economic regions. This document describes how it works and how to adopt it in your Overweb application.

## Overview

- **Tier 1** (full price): Higher-income countries (US, UK, Germany, Japan, etc.)
- **Tier 2** (30% discount): Middle-income countries (Brazil, Mexico, Poland, etc.)
- **Tier 3** (50% discount): Lower-income countries (India, Pakistan, Nigeria, etc.)

Tier is determined automatically from the user's phone number (E.164 country code) during verification.

## How It Works

1. User enters phone number (E.164 format).
2. OTP is sent via Twilio Verify.
3. On verification, country code is looked up in `PHONE_TIER_MAP`.
4. Price is calculated: `base_price * (1 - discount_pct/100)`.

## Enabling for a Project

In gov-hub, projects (layers/communities) can opt in:

- Set `offer_tier_pricing = True` on the `Project` model.
- When true, the Immortalize tab shows the Wizard option with tier pricing.
- When false, only Self-Service (Bitcoin) is shown.

## Adopting in Other Apps

1. **Copy the tier pricing module** (`tier_pricing.py`):
   - `PHONE_TIER_MAP` — country prefix to tier
   - `get_tier_for_phone(phone)` — returns 1, 2, or 3
   - `get_inscribe_price(page_count, image_count, tier, ...)` — returns price breakdown

2. **API shape** (for consistency across Overweb apps):
   - `POST /api/inscribe/calculate/` — `{page_count, image_count, tier}` → price breakdown
   - `POST /api/inscribe/send-otp/` — `{phone}` → sends OTP
   - `POST /api/inscribe/verify-otp/` — `{phone, code, page_count, image_count}` → tier + final price

3. **Config** (SiteConfig or equivalent):
   - `inscribe_price_per_page`, `inscribe_price_per_image`
   - `inscribe_tier2_discount`, `inscribe_tier3_discount` (percent)

## Acknowledgment Step

Before payment, users must acknowledge:

- "I acknowledge that times to receive may vary."
- Optional: "Notify me when my inscription is ready"

This sets expectations and enables notification opt-in.

## Submission Pending State

When payment succeeds, a `Submission` is created immediately with:

- `status = 'inscription_pending'`
- Tentative info (title, authors) shown to user
- Link to `InscriptionOrder` via `inscription_order_id`
- When inscription completes, `ordinalId` is filled and status updated

## References

- `tier_pricing.py` — reusable module
- `InscriptionOrder` model — stores tier, price, acknowledgment flags
- `Project.offer_tier_pricing` — community opt-in
