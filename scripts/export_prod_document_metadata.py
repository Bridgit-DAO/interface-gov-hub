#!/usr/bin/env python3
"""Export prod document category + tags by ml_number to JSON."""
import json
import os
import sys

PROD_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'gov-hub-prod'))
sys.path.insert(0, PROD_ROOT)
os.environ.setdefault('FLASK_ENV', 'production')

from app import app  # noqa: E402
from models import Submission  # noqa: E402
from services.layer_tags import tags_for_subject  # noqa: E402
from models.layer_tag import SUBJECT_SUBMISSION  # noqa: E402
from services.document_categories import normalize_document_category  # noqa: E402


def canonical_by_ml():
    approved = Submission.query.filter(
        Submission.status.in_(['approved', 'published']),
        Submission.ml_number.isnot(None),
    ).all()
    by_ml = {}
    for s in approved:
        ml = (s.ml_number or '').strip()
        if ml:
            by_ml.setdefault(ml, []).append(s)
    out = {}
    for ml, subs in by_ml.items():
        parents = [s for s in subs if not getattr(s, 'is_revision', False)] or subs
        with_wg = [s for s in parents if (s.group or '').strip()]
        pool = with_wg or parents
        pool.sort(key=lambda s: s.submitted_at or '', reverse=True)
        sub = pool[0]
        tags = tags_for_subject(SUBJECT_SUBMISSION, sub.id)
        out[ml] = {
            'submission_id': sub.id,
            'title': sub.title,
            'document_category': normalize_document_category(sub.document_category),
            'tag_slugs': [t['slug'] for t in tags],
        }
    return out


def main():
    out_path = os.environ.get('PROD_DOC_META_JSON', '/tmp/prod_document_metadata.json')
    with app.app_context():
        data = canonical_by_ml()
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, sort_keys=True)
    print(f'Exported {len(data)} families → {out_path}')


if __name__ == '__main__':
    main()
