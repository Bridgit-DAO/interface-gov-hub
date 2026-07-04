#!/usr/bin/env python3
"""Apply exported prod document metadata to dev by ml_number."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from extensions import db
from models import Submission
from services.document_categories import normalize_document_category
from services.layer_tags import set_submission_tags, sync_submission_tags_to_artifact


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
        out[ml] = pool[0]
    return out


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--json', default='/tmp/prod_document_metadata.json')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    with open(args.json, encoding='utf-8') as f:
        prod_meta = json.load(f)

    with app.app_context():
        dev_by_ml = canonical_by_ml()
        print(f'Prod families: {len(prod_meta)}  Dev families: {len(dev_by_ml)}')
        for ml, prod in sorted(prod_meta.items(), key=lambda x: x[0]):
            primary = dev_by_ml.get(ml)
            if not primary:
                print(f'  MISSING dev {ml} ({prod.get("title", "")[:50]})')
                continue
            cat = normalize_document_category(prod.get('document_category'))
            tags = prod.get('tag_slugs') or []
            print(f'  {ml}  {cat}  {tags}')
            if args.apply:
                approved = Submission.query.filter_by(ml_number=ml).filter(
                    Submission.status.in_(['approved', 'published'])
                ).all()
                for s in approved:
                    if not getattr(s, 'is_revision', False):
                        s.document_category = cat
                set_submission_tags(primary, tags, user_id=None)
                sync_submission_tags_to_artifact(primary)
        if args.apply:
            db.session.commit()
            print('✅ Dev metadata aligned to prod export.')


if __name__ == '__main__':
    main()
