"""Inspirational page heroes – hourly-cycling title + text with shared placeholder art."""
from __future__ import annotations

import html as html_mod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

# Select_3 fallback when target_image file is missing (see target_image per page).
HERO_PLACEHOLDER_IMAGE = '/static/images/hero-placeholder.png?v=1'
_STATIC_IMAGES_DIR = Path(__file__).resolve().parents[1] / 'static' / 'images'


class HeroMessage(TypedDict):
    title: str
    text: str


class PageHeroConfig(TypedDict, total=False):
    aria: str
    target_image: str
    messages: List[HeroMessage]


PAGE_HEROES: Dict[str, PageHeroConfig] = {
    'submit_draft': {
        'aria': 'Submit a draft to your layer',
        'target_image': '/static/images/hero-submit-draft.png?v=2',
        'messages': [
            {
                'title': 'Put your idea on the record',
                'text': 'A draft is more than a file – it is a claim that something should be true. Start here.',
            },
            {
                'title': 'Someone has to write it first',
                'text': 'The standards we live by began as a single submission. Yours could be next.',
            },
            {
                'title': 'Leave a trace that outlasts the moment',
                'text': 'What you submit today becomes part of how this layer thinks tomorrow.',
            },
        ],
    },
    'workgroups': {
        'aria': 'Workgroups across Gov Hub layers',
        'target_image': '/static/images/hero-workgroups.png?v=1',
        'messages': [
            {
                'title': 'Find the people doing the work',
                'text': 'Workgroups are where intent becomes action – join one, or start one.',
            },
            {
                'title': 'No one builds a layer alone',
                'text': 'The hardest problems are solved by people who show up together, again and again.',
            },
            {
                'title': 'There is a table with your name on it',
                'text': 'Browse workgroups across layers. The right one is waiting for your contribution.',
            },
        ],
    },
    'layers': {
        'aria': 'Browse layers on Gov Hub',
        'target_image': '/static/images/hero-layers.png?v=1',
        'messages': [
            {
                'title': 'Governance, one layer at a time',
                'text': 'Each layer is a living system – workgroups, roles, docs, and decisions stacked together.',
            },
            {
                'title': 'From local intent to shared infrastructure',
                'text': 'Layers let communities coordinate without losing what makes them distinct.',
            },
            {
                'title': 'Choose where you want to matter',
                'text': 'Pick a layer. Stay for the mission. Leave your mark on how it runs.',
            },
        ],
    },
    'docs_drafts': {
        'aria': 'Docs and drafts directory',
        'target_image': '/static/images/hero-docs-drafts.png?v=1',
        'messages': [
            {
                'title': 'Read what is being written',
                'text': 'Drafts are living arguments. RFCs are commitments. Browse both – then add yours.',
            },
            {
                'title': 'From draft to adopted',
                'text': 'Every document here is on a path: refine, collaborate, improve – until it belongs to the layer.',
            },
            {
                'title': 'The record of how we decided',
                'text': 'Docs and drafts are the memory of governance. Read them. Shape them. Leave your mark.',
            },
        ],
    },
    'roles': {
        'aria': 'Roles directory',
        'target_image': '/static/images/hero-roles.png?v=1',
        'messages': [
            {
                'title': 'Responsibility has a name',
                'text': 'Roles make work legible – discover what needs doing, and who can do it.',
            },
            {
                'title': 'Step into what you are ready to carry',
                'text': 'Claiming a role is not vanity. It is how layers know who to trust.',
            },
            {
                'title': 'Governance runs on people who show up',
                'text': 'Browse roles across layers. The right fit might be one click away.',
            },
        ],
    },
    'guilds': {
        'aria': 'Guilds directory',
        'target_image': '/static/images/hero-guilds.png?v=1',
        'messages': [
            {
                'title': 'Cross the boundaries that slow you down',
                'text': 'Guilds connect people across layers who share a craft, a cause, or a curiosity.',
            },
            {
                'title': 'Belong beyond a single layer',
                'text': 'Find collaborators who think like you – then build something neither layer could alone.',
            },
            {
                'title': 'Community is infrastructure too',
                'text': 'Guilds are where lasting relationships outlive any single project.',
            },
        ],
    },
    'votes': {
        'aria': 'Votes and elections',
        'target_image': '/static/images/hero-votes.png?v=2',
        'messages': [
            {
                'title': 'Decisions deserve witnesses',
                'text': 'Votes turn disagreement into outcome. Find elections where your voice counts.',
            },
            {
                'title': 'Show up when it matters',
                'text': 'The layers that endure are the ones whose people vote – and accept the result.',
            },
            {
                'title': 'Your ballot is a kind of authorship',
                'text': 'Browse votes by layer. Leave your mark on who leads and what passes.',
            },
        ],
    },
    'artifacts': {
        'aria': 'Artifacts and knowledge objects',
        'target_image': '/static/images/hero-artifacts.png?v=1',
        'messages': [
            {
                'title': 'Ideas that outlive the meeting',
                'text': 'Artifacts capture proposals, evidence, and submissions – the substance behind the talk.',
            },
            {
                'title': 'Build the layer\'s memory',
                'text': 'What gets artifacted gets referenced. What gets referenced shapes what happens next.',
            },
            {
                'title': 'Leave something that can be found',
                'text': 'Browse knowledge objects across layers. Add work worth returning to.',
            },
        ],
    },
    'opportunities': {
        'aria': 'Ways to contribute now',
        'target_image': '/static/images/hero-opportunities.png?v=1',
        'messages': [
            {
                'title': 'Something here needs you',
                'text': 'Open drafts, quests, and calls to contribute – find where your effort moves the needle.',
            },
            {
                'title': 'Do not wait for permission to help',
                'text': 'Opportunities are invitations with deadlines. Answer one today.',
            },
            {
                'title': 'Impact starts with showing up',
                'text': 'Browse layers for ways to participate. The right moment is often now.',
            },
        ],
    },
    'waitlists': {
        'aria': 'Waitlists across Gov Hub layers',
        'target_image': '/static/images/hero-waitlists.png?v=1',
        'messages': [
            {
                'title': 'Your place in line matters',
                'text': 'Join waitlists for launches, features, and cohorts – show up early, stay informed.',
            },
            {
                'title': 'Good things have a queue',
                'text': 'Reserve your spot before the door opens. Browse waitlists across layers.',
            },
            {
                'title': 'Be first when it goes live',
                'text': 'Waitlists turn anticipation into participation. Find one worth joining today.',
            },
        ],
    },
}


def hero_variant_index(page_key: str, *, hour: Optional[int] = None) -> int:
    cfg = PAGE_HEROES.get(page_key)
    if not cfg or not cfg.get('messages'):
        return 0
    h = datetime.utcnow().hour if hour is None else int(hour)
    return h % len(cfg['messages'])


def _resolve_hero_image(target: Optional[str]) -> str:
    """Use target art when the file exists; otherwise fall back to the placeholder."""
    if not target:
        return HERO_PLACEHOLDER_IMAGE
    path_part = target.split('?', 1)[0]
    if not path_part.startswith('/static/images/'):
        return HERO_PLACEHOLDER_IMAGE
    filename = path_part.rsplit('/', 1)[-1]
    if (_STATIC_IMAGES_DIR / filename).is_file():
        return target if '?' in target else f'{path_part}?v=1'
    return HERO_PLACEHOLDER_IMAGE


def pick_page_hero(page_key: str, *, hour: Optional[int] = None) -> Dict[str, Any]:
    """Return {title, text, image, aria, variant_index} for the current UTC hour."""
    cfg = PAGE_HEROES.get(page_key) or {}
    messages = cfg.get('messages') or [{'title': '', 'text': ''}]
    idx = hero_variant_index(page_key, hour=hour)
    msg = messages[idx]
    target = cfg.get('target_image') or HERO_PLACEHOLDER_IMAGE
    return {
        'title': msg.get('title', ''),
        'text': msg.get('text', ''),
        'image': _resolve_hero_image(target),
        'target_image': target,
        'aria': cfg.get('aria') or page_key.replace('_', ' '),
        'variant_index': idx,
    }


def render_page_hero_html(page_key: str, *, hour: Optional[int] = None) -> str:
    """Full-width hero banner with left-aligned cycling copy."""
    hero = pick_page_hero(page_key, hour=hour)
    if not hero.get('title'):
        return ''
    title = html_mod.escape(hero['title'])
    text = html_mod.escape(hero['text'])
    aria = html_mod.escape(hero['aria'])
    img = html_mod.escape(hero['image'], quote=True)
    return f'''
<section class="gh-page-hero" aria-label="{aria}">
    <div class="gh-page-hero-banner">
        <img
            src="{img}"
            alt=""
            width="1600"
            height="900"
            loading="eager"
            decoding="async"
            class="gh-page-hero-img"
        />
        <div class="gh-page-hero-overlay">
            <h2 class="gh-page-hero-title">{title}</h2>
            <p class="gh-page-hero-text">{text}</p>
        </div>
    </div>
</section>'''
