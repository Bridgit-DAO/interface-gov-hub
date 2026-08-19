"""Gov Hub public campaign pages – file-backed config (MVP)."""
from __future__ import annotations

import html as html_mod
import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional

from flask import has_app_context

from config import PROJECT_ROOT


CAMPAIGN_ROOT = os.path.join(PROJECT_ROOT, 'static', 'campaign')


@dataclass
class CampaignConfig:
    slug: str
    title: str
    subtitle: str
    hero_question: str
    hero_image_url: str
    layer_slug: str
    custom_domains: List[str]
    dev_host: str
    documents: List[Dict[str, Any]]
    external_links: List[Dict[str, Any]]
    primary_cta: Dict[str, str]
    secondary_ctas: List[Dict[str, str]]
    raw: Dict[str, Any]
    monument_id: Optional[str] = None
    presentation: Dict[str, Any] = None
    structure: Dict[str, Any] = None

    def hosts(self) -> frozenset:
        hosts = {h.lower().strip() for h in self.custom_domains if h}
        if self.dev_host:
            hosts.add(self.dev_host.lower().strip())
        return frozenset(hosts)

    def doc_by_slug(self, doc_slug: str) -> Optional[Dict[str, Any]]:
        for doc in self.documents:
            if doc.get('slug') == doc_slug:
                return doc
        return None

    def default_doc_slug(self) -> Optional[str]:
        for doc in self.documents:
            if doc.get('isDefault'):
                return doc.get('slug')
        for doc in self.documents:
            if doc.get('isPrimary'):
                return doc.get('slug')
        if self.documents:
            return self.documents[0].get('slug')
        return None


def _resolve_hero_image_url(data: Dict[str, Any], presentation: Optional[Dict[str, Any]] = None) -> str:
    pres = presentation or {}
    for source in (data, pres):
        for key in ('heroImageUrl', 'heroImage', 'hero_image_url'):
            value = (source.get(key) or '').strip()
            if value:
                return value
    return ''


def _parse_campaign(data: Dict[str, Any], slug: str) -> CampaignConfig:
    presentation = dict(data.get('presentation') or {})
    structure = dict(data.get('structure') or {})
    if not structure.get('nodes'):
        structure = build_monument_structure_from_seed(data)
    if not presentation:
        presentation = build_monument_presentation_from_seed(data)
    return CampaignConfig(
        slug=slug,
        title=data.get('title') or slug,
        subtitle=data.get('subtitle') or '',
        hero_question=data.get('heroQuestion') or '',
        hero_image_url=_resolve_hero_image_url(data, presentation),
        layer_slug=data.get('layerSlug') or '',
        custom_domains=list(data.get('customDomains') or []),
        dev_host=(data.get('devHost') or '').strip(),
        documents=list(data.get('documents') or []),
        external_links=list(data.get('externalLinks') or []),
        primary_cta=dict(data.get('primaryCta') or {}),
        secondary_ctas=list(data.get('secondaryCtas') or []),
        raw=data,
        presentation=presentation,
        structure=structure,
    )


def _safe_json(raw: Optional[str], fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return fallback


def _node_binding_to_doc(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    binding = node.get('binding') or {}
    participation = node.get('participation') or {}
    route = node.get('routeLegacy') or ''
    slug = node.get('slug') or ''
    if not route.startswith('/docs/') and binding.get('type') not in {'draft', 'markdown', 'pdf'}:
        return None

    doc = {
        'slug': slug,
        'label': node.get('label') or slug,
        'type': node.get('type') or node.get('kind') or binding.get('type'),
        'stage': node.get('stage') or node.get('status') or 'reference',
        'displayOrder': node.get('displayOrder') or node.get('order') or 0,
        'allowComments': bool(participation.get('comments')),
        'allowSuggestEdits': bool(participation.get('suggestEdits')),
        'allowEndorsement': bool(participation.get('endorsement')),
    }
    if binding.get('type') == 'draft':
        doc['draftRef'] = binding.get('draftRef')
    elif binding.get('type') == 'markdown':
        doc['contentPath'] = binding.get('path')
    elif binding.get('type') == 'pdf':
        doc['deckPath'] = binding.get('path')
    if node.get('isPrimary'):
        doc['isPrimary'] = True
    if node.get('isDefault'):
        doc['isDefault'] = True
    if node.get('ordinalInscriptionUrl'):
        doc['ordinalInscriptionUrl'] = node.get('ordinalInscriptionUrl')
    for key in ('thumbnailUrl', 'thumbnail', 'icon'):
        if node.get(key):
            doc[key] = node[key]
    return doc


def _external_links_from_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    links = []
    for node in nodes:
        binding = node.get('binding') or {}
        if binding.get('type') != 'external':
            continue
        links.append({
            'slug': node.get('slug'),
            'label': node.get('label'),
            'url': binding.get('url'),
            'description': node.get('description') or '',
            'displayOrder': node.get('displayOrder') or node.get('order') or 0,
            'type': node.get('type') or 'external',
            **{
                key: node[key]
                for key in ('thumbnailUrl', 'thumbnail', 'icon')
                if node.get(key)
            },
        })
    return links


def _parse_monument_campaign(monument) -> CampaignConfig:
    presentation = _safe_json(getattr(monument, 'presentation_json', None), {})
    structure = _safe_json(getattr(monument, 'structure_json', None), {})
    nodes = list(structure.get('nodes') or [])
    slug = (
        getattr(monument, 'campaign_slug', None)
        or presentation.get('campaignSlug')
        or str(getattr(monument, 'public_id', '') or getattr(monument, 'id', ''))
    )
    domains = _safe_json(getattr(monument, 'custom_domains_json', None), presentation.get('customDomains') or [])
    documents = [
        doc for doc in (_node_binding_to_doc(node) for node in nodes) if doc
    ]
    documents.sort(key=lambda item: item.get('displayOrder') or 0)
    external_links = list(presentation.get('externalLinks') or [])
    external_links.extend(_external_links_from_nodes(nodes))
    external_links.sort(key=lambda item: item.get('displayOrder') or 0)
    return CampaignConfig(
        slug=slug,
        title=presentation.get('title') or getattr(monument, 'title', None) or slug,
        subtitle=presentation.get('subtitle') or '',
        hero_question=presentation.get('heroQuestion') or '',
        hero_image_url=_resolve_hero_image_url(presentation),
        layer_slug=presentation.get('layerSlug') or '',
        custom_domains=list(domains or []),
        dev_host=presentation.get('devHost') or '',
        documents=documents,
        external_links=external_links,
        primary_cta=dict(presentation.get('primaryCta') or {}),
        secondary_ctas=list(presentation.get('secondaryCtas') or []),
        raw={
            'presentation': presentation,
            'structure': structure,
            'monument_id': getattr(monument, 'id', None),
        },
        monument_id=getattr(monument, 'id', None),
        presentation=presentation,
        structure=structure,
    )


def _load_monument_campaigns() -> Dict[str, CampaignConfig]:
    campaigns: Dict[str, CampaignConfig] = {}
    if not has_app_context():
        return campaigns
    try:
        from models import Monument

        rows = Monument.query.filter(Monument.campaign_slug.isnot(None)).all()
    except Exception:
        return campaigns
    for monument in rows:
        cfg = _parse_monument_campaign(monument)
        if cfg.slug:
            campaigns[cfg.slug] = cfg
    return campaigns


@lru_cache(maxsize=16)
def _load_all_campaigns() -> Dict[str, CampaignConfig]:
    campaigns: Dict[str, CampaignConfig] = _load_monument_campaigns()
    if not os.path.isdir(CAMPAIGN_ROOT):
        return campaigns
    for name in os.listdir(CAMPAIGN_ROOT):
        seed_path = os.path.join(CAMPAIGN_ROOT, name, 'campaign-seed.json')
        if not os.path.isfile(seed_path):
            continue
        with open(seed_path, encoding='utf-8') as handle:
            data = json.load(handle)
        slug = (data.get('slug') or name).strip()
        if slug not in campaigns:
            campaigns[slug] = _parse_campaign(data, slug)
    return campaigns


def get_campaign(slug: str) -> Optional[CampaignConfig]:
    return _load_all_campaigns().get(slug)


def campaign_for_host(host: str) -> Optional[CampaignConfig]:
    host_l = (host or '').split(',')[0].strip().split(':')[0].lower()
    for cfg in _load_all_campaigns().values():
        if host_l in cfg.hosts():
            return cfg
    return None


def reload_campaign_cache() -> None:
    _load_all_campaigns.cache_clear()


def campaign_base_path(slug: str) -> str:
    return f'/campaign/{slug}'


def campaign_href(slug: str, path: str = '/') -> str:
    """Path usable on campaign host (rewritten) or under /campaign/<slug>."""
    base = campaign_base_path(slug).rstrip('/')
    if not path or path == '/':
        return f'{base}/'
    if not path.startswith('/'):
        path = '/' + path
    return base + path


def resolve_project_path(rel_path: str) -> str:
    return os.path.join(PROJECT_ROOT, rel_path.replace('/', os.sep))


def build_monument_structure_from_seed(seed: Dict[str, Any]) -> Dict[str, Any]:
    """Convert the Phase 1 flat campaign seed into a book-monument node tree."""
    documents = {doc.get('slug'): doc for doc in seed.get('documents') or []}
    external = {item.get('slug'): item for item in seed.get('externalLinks') or []}

    def node(
        node_id: str,
        label: str,
        *,
        kind: str = 'page',
        parent_id: Optional[str] = None,
        status: str = 'stub',
        order: int = 0,
        binding: Optional[Dict[str, Any]] = None,
        participation: Optional[Dict[str, bool]] = None,
        route: Optional[str] = None,
        **extra,
    ) -> Dict[str, Any]:
        out = {
            'id': node_id,
            'slug': node_id,
            'label': label,
            'kind': kind,
            'status': status,
            'displayOrder': order,
        }
        if parent_id:
            out['parentId'] = parent_id
        if binding:
            out['binding'] = binding
        if participation:
            out['participation'] = participation
        if route:
            out['routeLegacy'] = route
        out.update({k: v for k, v in extra.items() if v is not None})
        return out

    paper = documents.get('paper') or {}
    statement = documents.get('statement') or {}
    slides = documents.get('slides') or {}
    substack = external.get('substack') or {}
    conference_talk = external.get('conference-talk') or {}

    nodes = [
        node('front-matter', 'Front Matter', kind='chapter', status='stub', order=0),
        node('welcome', 'Welcome', parent_id='front-matter', status='stub', order=1),
        node('authors', 'Authors', parent_id='front-matter', status='stub', order=2),
        node('participation-guide', 'Participation Guide', parent_id='front-matter', status='stub', order=3),
        node('chapter-1-teilhard-test', 'Chapter 1: The Teilhard Test', kind='chapter', status='active', order=10),
        node(
            'paper',
            paper.get('label') or 'Primary Paper',
            parent_id='chapter-1-teilhard-test',
            status='active',
            order=11,
            route='/docs/paper',
            binding={'type': 'draft', 'draftRef': paper.get('draftRef')},
            participation={
                'comments': bool(paper.get('allowComments')),
                'suggestEdits': bool(paper.get('allowSuggestEdits')),
                'endorsement': bool(paper.get('allowEndorsement')),
            },
            type=paper.get('type') or 'paper',
            stage=paper.get('stage'),
            isPrimary=paper.get('isPrimary'),
            isDefault=paper.get('isDefault'),
            ordinalInscriptionUrl=paper.get('ordinalInscriptionUrl'),
            thumbnailUrl=paper.get('thumbnailUrl'),
            icon=paper.get('icon'),
        ),
        node(
            'statement',
            statement.get('label') or 'Statement',
            parent_id='chapter-1-teilhard-test',
            status='active',
            order=12,
            route='/docs/statement',
            binding={'type': 'markdown', 'path': statement.get('contentPath')},
            participation={
                'comments': bool(statement.get('allowComments')),
                'suggestEdits': bool(statement.get('allowSuggestEdits')),
                'endorsement': bool(statement.get('allowEndorsement')),
            },
            type=statement.get('type') or 'statement',
            stage=statement.get('stage'),
            thumbnailUrl=statement.get('thumbnailUrl'),
            icon=statement.get('icon'),
        ),
        node(
            'slides',
            slides.get('label') or 'Slide Deck',
            parent_id='chapter-1-teilhard-test',
            status='active',
            order=13,
            route='/docs/slides',
            binding={'type': 'pdf', 'path': slides.get('deckPath')},
            participation={
                'comments': bool(slides.get('allowComments')),
                'suggestEdits': bool(slides.get('allowSuggestEdits')),
                'endorsement': bool(slides.get('allowEndorsement')),
            },
            type=slides.get('type') or 'slide_deck',
            stage=slides.get('stage'),
            thumbnailUrl=slides.get('thumbnailUrl'),
            icon=slides.get('icon'),
        ),
        node(
            'substack',
            substack.get('label') or 'Read on Substack',
            parent_id='chapter-1-teilhard-test',
            status='active',
            order=14,
            binding={'type': 'external', 'url': substack.get('url')},
            description=substack.get('description'),
            type='external',
            thumbnailUrl=substack.get('thumbnailUrl'),
            icon=substack.get('icon'),
        ),
        node(
            'conference-talk',
            conference_talk.get('label') or 'Conference Talk',
            parent_id='chapter-1-teilhard-test',
            status='active',
            order=15,
            binding={'type': 'external', 'url': conference_talk.get('url')},
            description=conference_talk.get('description'),
            type='external',
            thumbnailUrl=conference_talk.get('thumbnailUrl'),
            icon=conference_talk.get('icon'),
        ),
        node('chapter-2-core-concepts', 'Chapter 2: Core Concepts', kind='chapter', status='stub', order=20),
        node('chapter-3-perspectives', 'Chapter 3: Perspectives', kind='chapter', status='stub', order=30),
        node('teilhard-community', 'Teilhard Test Community', parent_id='chapter-3-perspectives', status='stub', order=31),
        node('meta-layer-initiative', 'Meta-Layer Initiative', parent_id='chapter-3-perspectives', status='stub', order=32),
        node('overweb', 'Overweb', parent_id='chapter-3-perspectives', status='stub', order=33),
        node('canopi', 'Canopi', parent_id='chapter-3-perspectives', status='stub', order=34),
        node('chapter-4-satplication', 'Chapter 4: The Satplication', kind='chapter', status='stub', order=40),
        node('chapter-5-applications', 'Chapter 5: Applications', kind='chapter', status='stub', order=50),
        node('chapter-6-critiques-open-questions', 'Chapter 6: Critiques and Open Questions', kind='chapter', status='stub', order=60),
        node('chapter-7-evolution', 'Chapter 7: Evolution', kind='chapter', status='stub', order=70),
    ]
    return {
        'schemaVersion': 1,
        'source': 'campaign-seed.json',
        'nodes': nodes,
    }


def build_monument_presentation_from_seed(seed: Dict[str, Any]) -> Dict[str, Any]:
    hero_image_url = _resolve_hero_image_url(seed)
    presentation = {
        'campaignSlug': seed.get('slug'),
        'title': seed.get('title'),
        'subtitle': seed.get('subtitle'),
        'heroQuestion': seed.get('heroQuestion'),
        'layerSlug': seed.get('layerSlug'),
        'customDomains': list(seed.get('customDomains') or []),
        'devHost': seed.get('devHost'),
        'primaryCta': dict(seed.get('primaryCta') or {}),
        'secondaryCtas': list(seed.get('secondaryCtas') or []),
        'homeSections': ['turing_teilhard', 'four_criteria', 'doc_grid'],
    }
    if hero_image_url:
        presentation['heroImageUrl'] = hero_image_url
    return presentation


def find_monument_node(cfg: CampaignConfig, node_slug: str) -> Optional[Dict[str, Any]]:
    for node in (cfg.structure or {}).get('nodes') or []:
        if node.get('slug') == node_slug or node.get('id') == node_slug:
            return node
    return None


def read_statement_html(cfg: CampaignConfig, doc: Dict[str, Any]) -> str:
    from services.submission_preview_md import markdown_to_safe_preview_html

    rel = doc.get('contentPath') or ''
    path = resolve_project_path(rel)
    if not os.path.isfile(path):
        return '<p class="text-muted">Statement content not found.</p>'
    with open(path, encoding='utf-8') as handle:
        text = handle.read()
    html = markdown_to_safe_preview_html(text)
    return html if html else f'<pre>{html_mod.escape(text)}</pre>'
