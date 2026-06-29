#!/usr/bin/env python3
"""Apply Model C category + unified layer tags to approved document families.

Matches by ml_number; picks one canonical submission per family (prefers row with workgroup, else newest approved parent).
Dry-run: python scripts/seed_document_tags.py
Apply:   python scripts/seed_document_tags.py --apply
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# (document_category, tag_slugs) per ML-Draft number
PROPOSALS = {
    'ML-Draft-001': (
        'policy',
        ['governance', 'meta-layer', 'ietf-inspired', 'foundational'],
    ),
    'ML-Draft-002': (
        'policy',
        ['desirable-property', 'ai', 'ai-governance', 'ai-safety', 'ethics', 'trust'],
    ),
    'ML-Draft-003': (
        'policy',
        ['desirable-property', 'ai', 'ai-governance', 'community-governance', 'participation'],
    ),
    'ML-Draft-004': (
        'policy',
        ['desirable-property', 'ai', 'ai-governance', 'ai-containment', 'security', 'trust'],
    ),
    'ML-Draft-005': (
        'document',
        ['research', 'philosophy', 'noosphere', 'collective-intelligence', 'evaluation-framework'],
    ),
    'ML-Draft-006': (
        'document',
        ['research', 'civic-memory', 'noosphere', 'ai', 'archives', 'provenance'],
    ),
    'ML-Draft-007': (
        'guide',
        ['civic-memory', 'artifacts', 'provenance', 'meta-layer', 'framework'],
    ),
    'ML-Draft-008': (
        'policy',
        ['desirable-property', 'authentication', 'identity', 'trust', 'accountability', 'federation'],
    ),
    'ML-Draft-009': (
        'policy',
        ['desirable-property', 'agency', 'empowerment', 'governance'],
    ),
    'ML-Draft-010': (
        'policy',
        ['desirable-property', 'governance', 'scale', 'adaptive-systems'],
    ),
    'ML-Draft-011': (
        'policy',
        ['desirable-property', 'privacy', 'data-sovereignty', 'security'],
    ),
    'ML-Draft-012': (
        'policy',
        ['desirable-property', 'identity', 'namespace', 'decentralized-infrastructure'],
    ),
    'ML-Draft-013': (
        'policy',
        ['desirable-property', 'commerce', 'economics', 'trust'],
    ),
    'ML-Draft-014': (
        'policy',
        ['desirable-property', 'interoperability', 'portability', 'semantics'],
    ),
    'ML-Draft-015': (
        'policy',
        ['desirable-property', 'community', 'governance-zones', 'participation'],
    ),
    'ML-Draft-016': (
        'policy',
        ['desirable-property', 'incentives', 'developer-community', 'economics'],
    ),
    'ML-Draft-017': (
        'policy',
        ['desirable-property', 'education', 'onboarding', 'literacy'],
    ),
    'ML-Draft-018': (
        'policy',
        ['desirable-property', 'trust', 'transparency', 'accountability'],
    ),
    'ML-Draft-019': (
        'policy',
        ['desirable-property', 'security', 'provenance', 'integrity'],
    ),
    'ML-Draft-020': (
        'policy',
        ['desirable-property', 'roadmap', 'milestones', 'accountability'],
    ),
    'ML-Draft-021': (
        'policy',
        ['desirable-property', 'sustainability', 'funding', 'economics'],
    ),
    'ML-Draft-022': (
        'policy',
        ['desirable-property', 'reputation', 'feedback', 'community'],
    ),
    'ML-Draft-023': (
        'policy',
        ['desirable-property', 'community-engagement', 'presence', 'growth'],
    ),
    'ML-Draft-024': (
        'policy',
        ['desirable-property', 'community-ownership', 'economics', 'governance'],
    ),
    'ML-Draft-025': (
        'policy',
        ['desirable-property', 'multimodal', 'ar', 'vr', 'xr', 'experience-design', 'accessibility'],
    ),
    'ML-Draft-026': (
        'guide',
        ['meta-layer', 'framework', 'overview', 'book-chapter', 'collective-intelligence'],
    ),
    'ML-Draft-027': (
        'document',
        ['civic-memory', 'research', 'design', 'sensemaking', 'meta-layer'],
    ),
    'ML-Draft-028': (
        'policy',
        ['desirable-property', 'civic-memory', 'sensemaking', 'epistemic-continuity'],
    ),
    'ML-Draft-029': (
        'policy',
        ['charter', 'governance', 'meta-layer', 'stewardship', 'collective-intelligence'],
    ),
}

# Title overrides when ml_number alone is ambiguous
TITLE_OVERRIDES = {
    'a future with civic memory design': (
        'document',
        ['civic-memory', 'research', 'design', 'sensemaking', 'meta-layer'],
    ),
    'the metaweb charter': (
        'policy',
        ['charter', 'governance', 'meta-layer', 'stewardship', 'collective-intelligence'],
    ),
}


def pick_canonical_submission(subs):
    """Prefer approved parent with workgroup, else first approved parent by submitted_at desc."""
    parents = [s for s in subs if not getattr(s, 'is_revision', False)]
    if not parents:
        parents = subs
    with_wg = [s for s in parents if (s.group or '').strip()]
    pool = with_wg or parents
    pool.sort(key=lambda s: s.submitted_at or '', reverse=True)
    return pool[0]


def resolve_proposal(submission):
    title_key = (submission.title or '').strip().lower()
    if title_key in TITLE_OVERRIDES:
        return TITLE_OVERRIDES[title_key]
    ml = (submission.ml_number or '').strip()
    if ml in PROPOSALS:
        return PROPOSALS[ml]
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Write to database')
    args = parser.parse_args()

    from app import app
    from extensions import db
    from models import Submission
    from services.document_categories import normalize_document_category
    from services.layer_tags import set_submission_tags, sync_submission_tags_to_artifact

    with app.app_context():
        approved = Submission.query.filter(
            Submission.status.in_(['approved', 'published']),
            Submission.ml_number.isnot(None),
        ).all()
        by_ml = {}
        for s in approved:
            ml = (s.ml_number or '').strip()
            if not ml:
                continue
            by_ml.setdefault(ml, []).append(s)

        print(f'Families: {len(by_ml)}  (dry_run={not args.apply})\n')
        for ml in sorted(by_ml.keys(), key=lambda x: int(x.split('-')[-1]) if x.split('-')[-1].isdigit() else 0):
            subs = by_ml[ml]
            sub = pick_canonical_submission(subs)
            prop = resolve_proposal(sub)
            if not prop:
                print(f'  SKIP {ml} — no proposal ({sub.title})')
                continue
            category, tags = prop
            category = normalize_document_category(category)
            print(f'  {ml}  {sub.id[:8]}…  {category}  tags={tags}')
            print(f'       title: {(sub.title or "")[:70]}')
            if args.apply:
                sub.document_category = category
                for s in subs:
                    if not getattr(s, 'is_revision', False):
                        s.document_category = category
                set_submission_tags(sub, tags, user_id=None)
                sync_submission_tags_to_artifact(sub)
        if args.apply:
            db.session.commit()
            print('\n✅ Applied categories and tags.')
        else:
            print('\n(dry run — use --apply to write)')


if __name__ == '__main__':
    main()
