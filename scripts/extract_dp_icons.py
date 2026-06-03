#!/usr/bin/env python3
"""Extract pictogram-only PNGs for DP workgroups from the master infographic."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
INFO_PATH = Path(
    '/home/ubuntu/.cursor/projects/home-ubuntu/assets/'
    'Desirable_Properties-51436a93-6018-400c-9602-4bb121f97e66.png'
)
CARD_DIR = Path('/home/ubuntu/.cursor/projects/home-ubuntu/assets/dp-icons')
STATIC_DP_DIR = REPO_ROOT / 'static' / 'images' / 'dp'
ICON_SIZE = 64
CARD_SLICE_W = 84
CARD_SLICE_H = 150
BODY_W = 66
BODY_H = 150

# Template-matched card origins on the master infographic (84×150 slices).
INFO_POSITIONS: dict[int, tuple[int, int]] = {
    1: (38, 125),
    2: (126, 125),
    3: (214, 125),
    4: (318, 125),
    5: (406, 125),
    6: (494, 125),
    7: (592, 125),
    8: (680, 125),
    9: (768, 125),
    10: (856, 125),
    11: (38, 295),
    12: (126, 295),
    13: (214, 295),
    14: (318, 295),
    15: (406, 295),
    16: (494, 295),
    17: (582, 295),
    21: (944, 125),
    22: (648, 295),
}

# Cards where infographic body contrast is too low or slices do not match.
SLICE_FALLBACK_DPS = frozenset({4, 5, 6, 18, 19, 20})
SLICE_TRIM_LEFT = 16
# Pictogram box inside trimmed 66×150 slice (below abbr, above title).
SLICE_ICON_BOX = (10, 68, 56, 118)
MATCH_DIFF_FALLBACK = 12.0

# Pictogram lives between label block and title block.
LABEL_BOTTOM_Y = 68
TITLE_TOP_Y = 96
BODY_MARGIN_X = (6, 8)  # trim card side borders

sys.path.insert(0, str(REPO_ROOT))
from services.groups import DP_ABBREVIATIONS  # noqa: E402


def _search_band(dp_num: int) -> tuple[int, int, int, int]:
    if dp_num <= 10 or dp_num == 21:
        return 115, 145, 10, 980
    if 11 <= dp_num <= 17 or dp_num == 22:
        return 275, 315, 10, 980
    return 412, 432, 280, 560


def match_card_on_infographic(
    info_rgb: np.ndarray,
    card_rgb: np.ndarray,
    *,
    y0: int,
    y1: int,
    x0: int,
    x1: int,
) -> tuple[int, int, float]:
    ih, iw = info_rgb.shape[:2]
    ch, cw = card_rgb.shape[:2]
    best = (1e9, 0, 0)
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 2):
            if y + ch > ih or x + cw > iw:
                continue
            patch = info_rgb[y : y + ch, x : x + cw].astype(np.int16)
            diff = float(np.mean(np.abs(patch - card_rgb.astype(np.int16))))
            if diff < best[0]:
                best = (diff, x, y)
    return best[1], best[2], best[0]


def pictogram_bbox(body_rgba: Image.Image) -> Image.Image:
    """Tight square crop around the pictogram via foreground detection."""
    arr = np.array(body_rgba)
    h, w = arr.shape[:2]
    ml, mr = BODY_MARGIN_X
    rgb = arr[:, :, :3].astype(np.float32)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    sat = np.max(rgb, axis=2) - np.min(rgb, axis=2)

    cyan_abbr = (g > 120) & (b > 120) & (r < 115)
    gold_abbr = (r > 130) & (g > 100) & (b < 100)
    white_txt = (lum > 195) & (sat < 50)

    fg = (lum > 78) & (sat > 14)
    fg &= ~cyan_abbr & ~gold_abbr & ~white_txt
    fg[:LABEL_BOTTOM_Y, :] = False
    fg[TITLE_TOP_Y:, :] = False
    fg[:, :ml] = False
    fg[:, max(0, w - mr) :] = False

    ys, xs = np.where(fg)
    if len(xs) < 16:
        side = int(min(w, h) * 0.44)
        cx, cy = int(w * 0.5), int(h * 0.56)
        left = max(0, cx - side // 2)
        top = max(0, cy - side // 2)
        return body_rgba.crop((left, top, min(w, left + side), min(h, top + side)))

    pad = 4
    left = int(max(0, np.percentile(xs, 10) - pad))
    right = int(min(w, np.percentile(xs, 90) + pad))
    top = int(max(0, np.percentile(ys, 10) - pad))
    bottom = int(min(h, np.percentile(ys, 90) + pad))
    side = max(right - left, bottom - top, 22)
    cx = (left + right) // 2
    cy = (top + bottom) // 2
    left = max(0, min(w - side, cx - side // 2))
    top = max(0, min(h - side, cy - side // 2))
    return body_rgba.crop((left, top, left + side, top + side))


def icon_from_body(body: Image.Image) -> Image.Image:
    crop = pictogram_bbox(body.convert('RGBA'))
    if crop.size != (ICON_SIZE, ICON_SIZE):
        crop = crop.resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
    return crop


def resolve_position(
    dp_num: int,
    abbr: str,
    info_rgb: np.ndarray,
) -> tuple[str, int, int, float]:
    if dp_num in INFO_POSITIONS:
        x, y = INFO_POSITIONS[dp_num]
        return 'infographic', x, y, 0.0
    card_path = CARD_DIR / f'DP{dp_num}_{abbr}.png'
    card_rgb = np.array(Image.open(card_path).convert('RGB'))
    y0, y1, x0, x1 = _search_band(dp_num)
    x, y, diff = match_card_on_infographic(info_rgb, card_rgb, y0=y0, y1=y1, x0=x0, x1=x1)
    return 'matched', x, y, diff


def card_body_from_infographic(info: Image.Image, x: int, y: int) -> Image.Image:
    return info.crop((x, y, x + BODY_W, y + BODY_H)).convert('RGBA')


def card_body_from_slice(card_path: Path) -> Image.Image:
    card = Image.open(card_path).convert('RGBA')
    left = min(SLICE_TRIM_LEFT, max(0, card.size[0] - BODY_W))
    return card.crop((left, 0, left + BODY_W, BODY_H))


def icon_from_slice_body(body: Image.Image) -> Image.Image:
    """Fixed pictogram window for card slices (avoids border/label false positives)."""
    l, t, r, b = SLICE_ICON_BOX
    w, h = body.size
    l, t = max(0, l), max(0, t)
    r, b = min(w, r), min(h, b)
    crop = body.crop((l, t, r, b))
    side = max(crop.size)
    cx = (l + r) // 2
    cy = (t + b) // 2
    left = max(0, min(w - side, cx - side // 2))
    top = max(0, min(h - side, cy - side // 2))
    square = body.crop((left, top, left + side, top + side))
    if square.size != (ICON_SIZE, ICON_SIZE):
        square = square.resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
    return square


def main() -> int:
    if not INFO_PATH.is_file():
        raise SystemExit(f'Missing infographic: {INFO_PATH}')

    info = Image.open(INFO_PATH)
    info_rgb = np.array(info.convert('RGB'))
    STATIC_DP_DIR.mkdir(parents=True, exist_ok=True)

    for dp_num, abbr in sorted(DP_ABBREVIATIONS.items()):
        source, x, y, diff = resolve_position(dp_num, abbr, info_rgb)
        use_slice = dp_num in SLICE_FALLBACK_DPS or (
            source == 'matched' and diff > MATCH_DIFF_FALLBACK
        )

        if use_slice:
            card_path = CARD_DIR / f'DP{dp_num}_{abbr}.png'
            if not card_path.is_file():
                raise SystemExit(f'Missing card slice: {card_path}')
            body = card_body_from_slice(card_path)
            icon = icon_from_slice_body(body)
            label = f'slice:{card_path.name}'
        else:
            body = card_body_from_infographic(info, x, y)
            icon = icon_from_body(body)
            label = f'infographic@{x},{y}'
        dest = STATIC_DP_DIR / f'dp{dp_num}.png'
        tmp = dest.with_suffix('.tmp.png')
        icon.save(tmp, optimize=True)
        tmp.replace(dest)
        print(f'dp{dp_num}: {icon.size} ({label}, diff={diff:.1f}) -> {dest}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
