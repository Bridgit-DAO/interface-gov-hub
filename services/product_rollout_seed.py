"""Seed and sync product_rollout from config/product_rollout.json (source of truth in repo)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from extensions import db
from models import SiteConfig
from services.product_rollout import PRODUCT_ROLLOUT_SITE_CONFIG_KEY, _coerce_bool_map

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROLLOUT_JSON_PATH = _REPO_ROOT / 'config' / 'product_rollout.json'


def load_rollout_json(path: Optional[Path] = None) -> Dict[str, bool]:
    """Load rollout flags from JSON file. Raises if file missing or invalid."""
    p = path or DEFAULT_ROLLOUT_JSON_PATH
    raw = json.loads(p.read_text(encoding='utf-8'))
    coerced = _coerce_bool_map(raw)
    if not coerced:
        raise ValueError(f'No valid rollout keys in {p}')
    return coerced


def rollout_json_payload(path: Optional[Path] = None) -> str:
    """Canonical JSON string for site_config storage."""
    cfg = load_rollout_json(path)
    return json.dumps(cfg, sort_keys=True)


def ensure_product_rollout_seeded(*, force: bool = False, path: Optional[Path] = None) -> bool:
    """
    Insert product_rollout from config/product_rollout.json when missing.
    Returns True if a row was written.
    When force=True, overwrite existing row with file contents.
    """
    payload = rollout_json_payload(path)
    row = SiteConfig.query.filter_by(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY).first()
    if row and not force:
        return False
    if row:
        row.value = payload
    else:
        db.session.add(SiteConfig(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY, value=payload))
    db.session.commit()
    return True
