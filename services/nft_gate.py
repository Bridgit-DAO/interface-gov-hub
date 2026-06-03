"""NFT-gated layer join: parse gate rules and verify wallet holdings."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

_LINE_RE = re.compile(
    r'^(eth|sol|btc)\s*:\s*(\S+)\s*$',
    re.IGNORECASE,
)


def parse_nft_gate_rules_text(text: str) -> Dict[str, List[dict]]:
    """Parse line-based rules into {eth, sol, btc} lists."""
    gate: Dict[str, List[dict]] = {'eth': [], 'sol': [], 'btc': []}
    for line in (text or '').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        chain, value = m.group(1).lower(), m.group(2).strip()
        if chain == 'eth':
            gate['eth'].append({'contract': value.lower()})
        elif chain == 'sol':
            gate['sol'].append({'mint': value})
        elif chain == 'btc':
            gate['btc'].append({'inscription_id': value})
    return gate


def dump_nft_gate_rules_text(gate: Optional[dict]) -> str:
    if not isinstance(gate, dict):
        return ''
    lines = []
    for entry in gate.get('eth') or []:
        if isinstance(entry, dict) and entry.get('contract'):
            lines.append(f"eth:{entry['contract']}")
    for entry in gate.get('sol') or []:
        if isinstance(entry, dict) and (entry.get('mint') or entry.get('collection')):
            lines.append(f"sol:{entry.get('mint') or entry.get('collection')}")
    for entry in gate.get('btc') or []:
        if isinstance(entry, dict) and entry.get('inscription_id'):
            lines.append(f"btc:{entry['inscription_id']}")
    return '\n'.join(lines)


def load_layer_nft_gate(layer) -> dict:
    raw = getattr(layer, 'nft_gate_json', None) or ''
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def save_layer_nft_gate(layer, gate: dict) -> None:
    layer.nft_gate_json = json.dumps(gate, sort_keys=True) if gate else None


def gate_has_requirements(gate: dict) -> bool:
    if not gate:
        return False
    for key in ('eth', 'sol', 'btc'):
        if gate.get(key):
            return True
    return False


def user_meets_nft_gate(user, gate: dict) -> Tuple[bool, Optional[str]]:
    """Return (ok, error_message). Any matching chain requirement grants access."""
    if not gate_has_requirements(gate):
        return True, None

    eth_req = gate.get('eth') or []
    sol_req = gate.get('sol') or []
    btc_req = gate.get('btc') or []

    if eth_req and not (user.evmAddress or '').strip():
        return False, 'Connect an Ethereum wallet on your profile to join this layer.'
    if sol_req and not (user.solanaAddress or '').strip():
        return False, 'Connect a Solana wallet on your profile to join this layer.'
    if btc_req and not (getattr(user, 'bitcoinAddress', None) or '').strip():
        return False, 'Your badge wallet (Bitcoin) is required to join this layer. Sign in again to provision it.'

    if eth_req and _eth_holds_any(user.evmAddress, eth_req):
        return True, None
    if sol_req and _sol_holds_any(user.solanaAddress, sol_req):
        return True, None
    if btc_req and _btc_holds_any(getattr(user, 'bitcoinAddress', None), btc_req):
        return True, None

    return False, 'You do not hold a required NFT from this layer\'s allow list.'


def _eth_holds_any(address: str, requirements: List[dict]) -> bool:
    api_key = (os.environ.get('ALCHEMY_API_KEY') or '').strip()
    if not api_key:
        return False
    contracts = [
        (r.get('contract') or '').lower()
        for r in requirements
        if isinstance(r, dict) and r.get('contract')
    ]
    if not contracts:
        return False
    url = f'https://eth-mainnet.g.alchemy.com/nft/v3/{api_key}/getNFTsForOwner'
    try:
        resp = requests.get(
            url,
            params={'owner': address, 'contractAddresses[]': contracts, 'withMetadata': 'false'},
            timeout=12,
        )
        if resp.status_code != 200:
            return False
        data = resp.json()
        owned = data.get('ownedNfts') or data.get('ownedNft') or []
        if owned:
            return True
        total = data.get('totalCount')
        return bool(total and int(total) > 0)
    except Exception:
        return False


def _sol_holds_any(address: str, requirements: List[dict]) -> bool:
    api_key = (os.environ.get('HELIUS_API_KEY') or '').strip()
    mints = [
        r.get('mint') or r.get('collection')
        for r in requirements
        if isinstance(r, dict) and (r.get('mint') or r.get('collection'))
    ]
    if not mints:
        return False
    if api_key:
        try:
            resp = requests.post(
                f'https://api.helius.xyz/v0/addresses/{address}/balances?api-key={api_key}',
                json={'displayOptions': {'showFungible': False}},
                timeout=12,
            )
            if resp.status_code == 200:
                tokens = (resp.json() or {}).get('tokens') or []
                mint_set = {m for m in mints}
                for t in tokens:
                    if t.get('mint') in mint_set:
                        return True
        except Exception:
            pass
    return False


def _btc_holds_any(address: str, requirements: List[dict]) -> bool:
    api_key = (os.environ.get('UNISAT_API_KEY') or '').strip()
    if not api_key or not address:
        return False
    allowed = {
        (r.get('inscription_id') or '').strip()
        for r in requirements
        if isinstance(r, dict) and r.get('inscription_id')
    }
    if not allowed:
        return False
    base = (
        'https://open-api-testnet.unisat.io'
        if os.environ.get('UNISAT_TESTNET')
        else 'https://open-api.unisat.io'
    )
    cursor = 0
    size = 60
    try:
        for _ in range(5):
            resp = requests.get(
                f'{base}/v1/indexer/address/{address}/inscription-data',
                params={'cursor': cursor, 'size': size},
                headers={'Authorization': f'Bearer {api_key}'},
                timeout=15,
            )
            if resp.status_code != 200:
                return False
            body = resp.json()
            if body.get('code') != 0:
                return False
            payload = body.get('data') or {}
            for item in payload.get('inscription') or []:
                iid = (item.get('inscriptionId') or item.get('inscription_id') or '').strip()
                if iid in allowed:
                    return True
            cursor = payload.get('cursor')
            if not cursor:
                break
    except Exception:
        return False
    return False
