"""Unified layer-scoped tags for artifacts, submissions, and future subjects."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import func

from extensions import db
from models import Artifact, LayerTag, LayerTagLink, Submission
from models.layer_tag import SUBJECT_ARTIFACT, SUBJECT_SUBMISSION

SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
MAX_TAGS_PER_SUBJECT = 10
MAX_SLUG_LEN = 48
MAX_LABEL_LEN = 64


def tags_enabled(config) -> bool:
    if config.get('LAYER_TAGS_ENABLED') is not None:
        return bool(config.get('LAYER_TAGS_ENABLED'))
    return bool(config.get('ARTIFACT_TAGS_ENABLED', True))


def tag_filters_enabled(config) -> bool:
    if not tags_enabled(config):
        return False
    if config.get('LAYER_TAG_FILTERS_ENABLED') is not None:
        return bool(config.get('LAYER_TAG_FILTERS_ENABLED'))
    return bool(config.get('ARTIFACT_TAG_FILTERS_ENABLED', True))


def document_tags_enabled(config) -> bool:
    if config.get('DOCUMENT_TAGS_ENABLED') is not None:
        return bool(config.get('DOCUMENT_TAGS_ENABLED'))
    return tags_enabled(config)


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


# Whole-token acronyms when deriving display labels from slugs (e.g. ai-governance → AI Governance).
_LABEL_ACRONYMS = frozenset({
    'ai', 'ar', 'vr', 'xr', 'api', 'url', 'uri', 'id', 'ietf', 'ml',
})


def slug_to_label(slug: str) -> str:
    parts: List[str] = []
    for w in slug.split('-'):
        if not w:
            continue
        low = w.lower()
        if low in _LABEL_ACRONYMS:
            parts.append(low.upper())
        else:
            parts.append(w.capitalize())
    return ' '.join(parts)


def parse_tag_slugs(raw) -> List[str]:
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
    return out[:MAX_TAGS_PER_SUBJECT]


def get_or_create_tag(layer_id: str, slug: str, user_id: Optional[str], label: Optional[str] = None) -> LayerTag:
    tag = LayerTag.query.filter_by(layer_id=layer_id, slug=slug).first()
    if tag:
        return tag
    tag = LayerTag(
        layer_id=layer_id,
        slug=slug,
        label=(label or slug_to_label(slug))[:MAX_LABEL_LEN],
        created_by_user_id=user_id,
    )
    db.session.add(tag)
    db.session.flush()
    return tag


def tags_for_subject(subject_type: str, subject_id: str) -> List[Dict[str, Any]]:
    rows = (
        db.session.query(LayerTag)
        .join(LayerTagLink, LayerTagLink.tag_id == LayerTag.id)
        .filter(
            LayerTagLink.subject_type == subject_type,
            LayerTagLink.subject_id == subject_id,
        )
        .order_by(LayerTag.label.asc())
        .all()
    )
    return [t.to_dict() for t in rows]


def tags_by_subject_ids(subject_type: str, subject_ids: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    if not subject_ids:
        return {}
    rows = (
        db.session.query(LayerTagLink.subject_id, LayerTag)
        .join(LayerTag, LayerTag.id == LayerTagLink.tag_id)
        .filter(
            LayerTagLink.subject_type == subject_type,
            LayerTagLink.subject_id.in_(list(subject_ids)),
        )
        .order_by(LayerTag.label.asc())
        .all()
    )
    out: Dict[str, List[Dict[str, Any]]] = {sid: [] for sid in subject_ids}
    for subject_id, tag in rows:
        out.setdefault(subject_id, []).append(tag.to_dict())
    return out


def list_layer_tags(layer_id: str, with_counts: bool = True) -> List[Dict[str, Any]]:
    if not with_counts:
        tags = LayerTag.query.filter_by(layer_id=layer_id).order_by(LayerTag.label.asc()).all()
        return [t.to_dict() for t in tags]

    tags = LayerTag.query.filter_by(layer_id=layer_id).order_by(LayerTag.label.asc()).all()
    if not tags:
        return []
    tag_ids = [t.id for t in tags]
    count_rows = (
        db.session.query(
            LayerTagLink.tag_id,
            LayerTagLink.subject_type,
            func.count(LayerTagLink.id),
        )
        .filter(LayerTagLink.tag_id.in_(tag_ids))
        .group_by(LayerTagLink.tag_id, LayerTagLink.subject_type)
        .all()
    )
    counts: Dict[str, Dict[str, int]] = {tid: {} for tid in tag_ids}
    for tag_id, stype, cnt in count_rows:
        counts.setdefault(tag_id, {})[stype or ''] = int(cnt or 0)
    out = []
    for t in tags:
        c = counts.get(t.id, {})
        d = t.to_dict(link_counts={
            'artifact': c.get(SUBJECT_ARTIFACT, 0),
            'submission': c.get(SUBJECT_SUBMISSION, 0),
        })
        out.append(d)
    return out


def set_subject_tags(
    subject_type: str,
    subject_id: str,
    layer_id: Optional[str],
    tag_slugs: Sequence[str],
    user_id: Optional[str],
) -> Tuple[Set[str], Set[str]]:
    if not layer_id:
        if tag_slugs:
            raise ValueError('Subjects without a layer cannot be tagged')
        return set(), set()

    desired = list(parse_tag_slugs(tag_slugs))
    existing_links = LayerTagLink.query.filter_by(
        subject_type=subject_type,
        subject_id=subject_id,
    ).all()
    existing_by_slug: Dict[str, LayerTagLink] = {}
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
        tag = get_or_create_tag(layer_id, slug, user_id)
        db.session.add(
            LayerTagLink(
                subject_type=subject_type,
                subject_id=subject_id,
                tag_id=tag.id,
                created_by_user_id=user_id,
            )
        )

    db.session.flush()
    return added, removed


def set_artifact_tags(artifact: Artifact, tag_slugs: Sequence[str], user_id: Optional[str]) -> Tuple[Set[str], Set[str]]:
    return set_subject_tags(SUBJECT_ARTIFACT, artifact.id, artifact.layer_id, tag_slugs, user_id)


def set_submission_tags(
    submission: Submission,
    tag_slugs: Sequence[str],
    user_id: Optional[str],
) -> Tuple[Set[str], Set[str]]:
    return set_subject_tags(
        SUBJECT_SUBMISSION,
        submission.id,
        submission.layer_id,
        tag_slugs,
        user_id,
    )


def sync_submission_tags_to_artifact(submission: Submission) -> None:
    """Mirror submission tags onto linked artifact (unified vocabulary)."""
    if not submission.artifact_id or not submission.layer_id:
        return
    slugs = [t['slug'] for t in tags_for_subject(SUBJECT_SUBMISSION, submission.id)]
    set_subject_tags(
        SUBJECT_ARTIFACT,
        submission.artifact_id,
        submission.layer_id,
        slugs,
        None,
    )


def apply_tag_filter(
    query,
    tag_slugs: Sequence[str],
    *,
    subject_type: str = SUBJECT_ARTIFACT,
    match_any: bool = False,
):
    """Filter a query whose model id matches layer_tag_link.subject_id."""
    slugs = parse_tag_slugs(tag_slugs)
    if not slugs:
        return query
    model = query.column_descriptions[0]['entity']
    id_col = model.id
    if match_any:
        return query.filter(
            id_col.in_(
                db.session.query(LayerTagLink.subject_id)
                .join(LayerTag, LayerTag.id == LayerTagLink.tag_id)
                .filter(
                    LayerTagLink.subject_type == subject_type,
                    LayerTag.slug.in_(slugs),
                )
                .distinct()
            )
        )
    for slug in slugs:
        sub = (
            db.session.query(LayerTagLink.subject_id)
            .join(LayerTag, LayerTag.id == LayerTagLink.tag_id)
            .filter(
                LayerTagLink.subject_type == subject_type,
                LayerTag.slug == slug,
            )
        )
        query = query.filter(id_col.in_(sub))
    return query


def tags_for_artifact(artifact_id: str) -> List[Dict[str, Any]]:
    return tags_for_subject(SUBJECT_ARTIFACT, artifact_id)


def tags_by_artifact_ids(artifact_ids: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    return tags_by_subject_ids(SUBJECT_ARTIFACT, artifact_ids)


def artifact_to_dict(artifact: Artifact, include_tags: bool = True) -> Dict[str, Any]:
    d = artifact.to_dict()
    d['tags'] = tags_for_artifact(artifact.id) if include_tags else []
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
