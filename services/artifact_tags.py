"""Layer-scoped artifact tags: normalize, assign, filter, serialize."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import func

from extensions import db
from models import Artifact, ArtifactTag, ArtifactTagLink

SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
MAX_TAGS_PER_ARTIFACT = 10
MAX_SLUG_LEN = 48
MAX_LABEL_LEN = 64


def tags_enabled(config) -> bool:
    return bool(config.get('ARTIFACT_TAGS_ENABLED', True))


def tag_filters_enabled(config) -> bool:
    return tags_enabled(config) and bool(config.get('ARTIFACT_TAG_FILTERS_ENABLED', True))


def normalize_slug(value: str) -> Optional[str]:
    if not value or not str(value).strip():
        return None
    s = str(value).strip().lower()
    s = re.sub(r'[\s_]+', '-', s)
    s = re.sub(r'[^a-z0-9-]', '', s)
    s = re.sub(r'-+', '-', s).strip('-')
    if len(s) < 2 or len(s) > MAX_SLUG_LEN or not SLUG_RE.match(s):
        return None
    return s


def slug_to_label(slug: str) -> str:
    return ' '.join(w.capitalize() for w in slug.split('-') if w)


def parse_tag_slugs(raw) -> List[str]:
    """Accept list of slugs/labels or comma-separated string."""
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split(',') if p.strip()]
    elif isinstance(raw, (list, tuple)):
        parts = [str(p).strip() for p in raw if str(p).strip()]
    else:
        return []
    out: List[str] = []
    seen: Set[str] = set()
    for p in parts:
        slug = normalize_slug(p)
        if not slug:
            slug = normalize_slug(p.lower().replace(' ', '-'))
        if slug and slug not in seen:
            seen.add(slug)
            out.append(slug)
    return out[:MAX_TAGS_PER_ARTIFACT]


def get_or_create_tag(layer_id: str, slug: str, user_id: Optional[str], label: Optional[str] = None) -> ArtifactTag:
    tag = ArtifactTag.query.filter_by(layer_id=layer_id, slug=slug).first()
    if tag:
        return tag
    tag = ArtifactTag(
        layer_id=layer_id,
        slug=slug,
        label=(label or slug_to_label(slug))[:MAX_LABEL_LEN],
        created_by_user_id=user_id,
    )
    db.session.add(tag)
    db.session.flush()
    return tag


def tags_for_artifact(artifact_id: str) -> List[Dict[str, Any]]:
    rows = (
        db.session.query(ArtifactTag)
        .join(ArtifactTagLink, ArtifactTagLink.tag_id == ArtifactTag.id)
        .filter(ArtifactTagLink.artifact_id == artifact_id)
        .order_by(ArtifactTag.label.asc())
        .all()
    )
    return [t.to_dict() for t in rows]


def tags_by_artifact_ids(artifact_ids: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    if not artifact_ids:
        return {}
    rows = (
        db.session.query(ArtifactTagLink.artifact_id, ArtifactTag)
        .join(ArtifactTag, ArtifactTag.id == ArtifactTagLink.tag_id)
        .filter(ArtifactTagLink.artifact_id.in_(list(artifact_ids)))
        .order_by(ArtifactTag.label.asc())
        .all()
    )
    out: Dict[str, List[Dict[str, Any]]] = {aid: [] for aid in artifact_ids}
    for artifact_id, tag in rows:
        out.setdefault(artifact_id, []).append(tag.to_dict())
    return out


def list_layer_tags(layer_id: str, with_counts: bool = True) -> List[Dict[str, Any]]:
    if with_counts:
        rows = (
            db.session.query(
                ArtifactTag,
                func.count(ArtifactTagLink.id).label('artifact_count'),
            )
            .outerjoin(ArtifactTagLink, ArtifactTagLink.tag_id == ArtifactTag.id)
            .filter(ArtifactTag.layer_id == layer_id)
            .group_by(ArtifactTag.id)
            .order_by(ArtifactTag.label.asc())
            .all()
        )
        return [t.to_dict(artifact_count=int(c or 0)) for t, c in rows]
    tags = ArtifactTag.query.filter_by(layer_id=layer_id).order_by(ArtifactTag.label.asc()).all()
    return [t.to_dict() for t in tags]


def set_artifact_tags(
    artifact: Artifact,
    tag_slugs: Sequence[str],
    user_id: Optional[str],
) -> Tuple[Set[str], Set[str]]:
    """
    Replace artifact's tags with tag_slugs. Returns (added_slugs, removed_slugs).
    Requires artifact.layer_id.
    """
    if not artifact.layer_id:
        if tag_slugs:
            raise ValueError('Artifacts without a layer cannot be tagged')
        return set(), set()

    desired = list(parse_tag_slugs(tag_slugs))
    existing_links = ArtifactTagLink.query.filter_by(artifact_id=artifact.id).all()
    existing_by_slug: Dict[str, ArtifactTagLink] = {}
    for link in existing_links:
        if link.tag:
            existing_by_slug[link.tag.slug] = link

    desired_set = set(desired)
    existing_set = set(existing_by_slug.keys())
    removed = existing_set - desired_set
    added = desired_set - existing_set

    for slug in removed:
        db.session.delete(existing_by_slug[slug])

    for slug in desired:
        if slug in existing_by_slug:
            continue
        tag = get_or_create_tag(artifact.layer_id, slug, user_id)
        db.session.add(
            ArtifactTagLink(
                artifact_id=artifact.id,
                tag_id=tag.id,
                created_by_user_id=user_id,
            )
        )

    db.session.flush()
    return added, removed


def apply_tag_filter(query, tag_slugs: Sequence[str], match_any: bool = False):
    """Filter Artifact query by tag slugs (AND default, OR if match_any)."""
    slugs = parse_tag_slugs(tag_slugs)
    if not slugs:
        return query
    if match_any:
        return query.filter(
            Artifact.id.in_(
                db.session.query(ArtifactTagLink.artifact_id)
                .join(ArtifactTag, ArtifactTag.id == ArtifactTagLink.tag_id)
                .filter(ArtifactTag.slug.in_(slugs))
                .distinct()
            )
        )
    for slug in slugs:
        sub = (
            db.session.query(ArtifactTagLink.artifact_id)
            .join(ArtifactTag, ArtifactTag.id == ArtifactTagLink.tag_id)
            .filter(ArtifactTag.slug == slug)
        )
        query = query.filter(Artifact.id.in_(sub))
    return query


def artifact_to_dict(artifact: Artifact, include_tags: bool = True) -> Dict[str, Any]:
    d = artifact.to_dict()
    if include_tags:
        d['tags'] = tags_for_artifact(artifact.id)
    else:
        d['tags'] = []
    return d


def enrich_artifact_dicts(artifacts: Sequence[Artifact]) -> List[Dict[str, Any]]:
    ids = [a.id for a in artifacts]
    tag_map = tags_by_artifact_ids(ids)
    out = []
    for a in artifacts:
        d = a.to_dict()
        d['tags'] = tag_map.get(a.id, [])
        out.append(d)
    return out
