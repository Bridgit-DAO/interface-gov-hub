#!/usr/bin/env python3
"""Smoke tests for soft-launch routes and fixture API."""
import sys

sys.path.insert(0, '.')

from app import app


def test_soft_launch_routes():
    with app.app_context():
        c = app.test_client()
        home_paths = ('/soft-launch', '/soft-launch/')
        for path in home_paths:
            r = c.get(path)
            assert r.status_code == 200, (path, r.status_code)
            text = r.get_data(as_text=True)
            for needle in (
                'data-gh-i18n="softLaunch.home.headline"',
                'data-gh-i18n="softLaunch.home.subtext"',
                'data-gh-i18n="softLaunch.home.participationTitle"',
                'data-gh-i18n="softLaunch.participation.shareCta"',
                'data-gh-i18n="softLaunch.home.monumentTitle"',
                'data-gh-i18n="softLaunch.home.monumentCtaPrimary"',
                'data-gh-i18n="softLaunch.home.monumentCtaSecondary"',
                'soft-launch.css',
                'soft-launch-page',
            ):
                assert needle in text, (path, needle)

        for path, needle in [
            ('/soft-launch/onboarding/', 'data-gh-i18n="softLaunch.onboarding.step1Title"'),
            ('/soft-launch/onboarding/', 'data-gh-i18n="softLaunch.onboarding.step4BrickHeadline"'),
            ('/soft-launch/artifact/', 'data-gh-i18n="softLaunch.artifact.demo.title"'),
            ('/soft-launch/artifact/?scenario=vote_open', 'data-gh-i18n="softLaunch.artifact.castVoteHeading"'),
            ('/soft-launch/artifact/?scenario=draft', 'data-gh-i18n="softLaunch.status.draft"'),
        ]:
            r = c.get(path)
            assert r.status_code == 200, (path, r.status_code)
            text = r.get_data(as_text=True)
            assert needle in text, (path, needle)

        j = c.get('/api/soft-launch/fixtures/')
        assert j.status_code == 200
        data = j.get_json()
        assert data['homepage']['headline']
        assert data['homepage']['monument']['title'] == 'Build the Monument'
        assert 'participation_cards' in data
        assert len(data['participation_cards']) == 3
        assert 'artifacts' in data
        assert 'under_review' in data['artifacts']
        assert 'draft' in data['artifacts']

        lc = c.get('/api/soft-launch/lifecycle/')
        assert lc.status_code == 200
        stages = lc.get_json()['stages']
        assert len(stages) >= 6
        assert stages[0]['status'] == 'draft'


if __name__ == '__main__':
    test_soft_launch_routes()
    print('test_soft_launch_scaffolding: ok')
