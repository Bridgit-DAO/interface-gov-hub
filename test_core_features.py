#!/usr/bin/env python3
"""
Core Feature Verification Tests
Run this before commits to ensure critical functionality works
"""

import sys
import os
sys.path.append('.')

import pytest

from app import app
from models import User
from services.documents import COMMENTS

def test_critical_features():
    """Test all critical application features"""
    print("🧪 Testing Core MLTF Datatracker Features...")
    print("=" * 50)

    with app.app_context():
        client = app.test_client()

        # 1. Authentication: login page is GET-only (Web3Auth); no password form POST
        print("1. 🔐 Testing Authentication...")
        response = client.get('/login/')
        assert response.status_code == 200, "Login page should load"
        text_login = response.get_data(as_text=True)
        assert 'Sign In' in text_login or 'Web3Auth' in text_login

        # Exercise authenticated flows via session (same pattern as other tests)
        user_row = (
            User.query.filter(User.role.in_(['admin', 'editor'])).first()
            or User.query.first()
        )
        if not user_row:
            pytest.skip("No users in DB — seed data needed for full core feature test")
        with client.session_transaction() as sess:
            sess['user'] = user_row.username
        print("   ✅ Login page OK; session set for follow-on checks")

        # 2. Admin Dashboard
        print("2. 📊 Testing Admin Dashboard...")
        response = client.get('/admin/')
        assert response.status_code == 200
        assert 'Admin Dashboard' in response.get_data(as_text=True)
        print("   ✅ Admin dashboard accessible")

        # 3. Registration disabled (Web3Auth-only onboarding)
        print("3. 👥 Testing registration is disabled...")
        response = client.get('/register/', follow_redirects=True)
        assert response.status_code == 200, f"register redirect: {response.status_code}"
        text_register = response.get_data(as_text=True)
        assert 'Sign In' in text_register or 'Web3Auth' in text_register
        print("   ✅ Public registration blocked; redirects to sign-in")

        # 4. Document System
        print("4. 📄 Testing Document System...")
        response = client.get('/doc/all/')
        assert 'Documents' in response.get_data(as_text=True)
        assert 'Submit Draft' in response.get_data(as_text=True)
        print("   ✅ Document listing works")

        # 5. Individual Draft Pages
        print("5. 📋 Testing Individual Draft Pages...")
        # Check if we have any drafts/submissions first
        from models import Submission
        has_drafts = Submission.query.count() > 0

        if has_drafts:
            # Test with first available draft
            first_submission = Submission.query.first()
            if first_submission:
                draft_ref = first_submission.draft_name or first_submission.id
                response = client.get(f'/doc/draft/{draft_ref}/')
                assert draft_ref in response.get_data(as_text=True)
                print("   ✅ Individual draft page works")
        else:
            # No drafts available - test that the route doesn't crash
            response = client.get('/doc/draft/nonexistent-draft/')
            assert response.status_code == 404
            print("   ✅ Draft route handles missing drafts gracefully")

        # 6. Comment System
        print("6. 💬 Testing Comment System...")
        comment_count = sum(len(comments) for comments in COMMENTS.values())
        print(f"   📊 {comment_count} total comments in system")

        # Test comment functionality (skip submission if no drafts)
        if has_drafts:
            # Test comment submission on first available draft
            draft_name = None
            first_submission = Submission.query.first()
            if first_submission:
                draft_name = first_submission.draft_name
            if first_submission:
                draft_name = first_submission.draft_name or first_submission.id

            if draft_name:
                response = client.post(f'/doc/draft/{draft_name}/comments/',
                                      data={'comment': 'Automated test comment'})
                assert response.status_code in (200, 302)
                print("   ✅ Comment submission works")

                # Test comment display
                response = client.get(f'/doc/draft/{draft_name}/comments/')
                assert 'Add a Comment' in response.get_data(as_text=True)
                print("   ✅ Comment display with form works")
            else:
                print("   ⚠️  No drafts available for comment testing")
        else:
            # Test comment route accessibility without drafts
            response = client.get('/doc/draft/nonexistent-draft/comments/')
            assert response.status_code == 404
            print("   ✅ Comment routes handle missing drafts gracefully")

        # 7. Submission System
        print("7. 📤 Testing Submission System...")
        response = client.get('/submit/')
        assert response.status_code == 200
        assert 'Submit a Meta-Layer Draft' in response.get_data(as_text=True)
        print("   ✅ Submission form accessible")

        # 8. Workgroups (route: /group/)
        print("8. 🏢 Testing Workgroups...")
        response = client.get('/group/')
        text_group = response.get_data(as_text=True)
        assert response.status_code == 200
        assert 'Workgroup' in text_group  # page title uses "Workgroups"
        print("   ✅ Workgroups page works")

        # 9. Coordinator / chairs admin
        print("9. 👑 Testing coordinator management...")
        response = client.get('/admin/chairs/')
        assert response.status_code == 200
        assert 'Coordinator Management' in response.get_data(as_text=True)
        print("   ✅ Coordinator management accessible")

        # 10. Theme System
        print("10. 🌙 Testing Theme System...")
        # Theme system is not implemented in this simplified version
        # This is expected and not a failure
        print("   ℹ️  Theme system not implemented (simplified version)")

        print("=" * 50)
        print("🎉 ALL CRITICAL FEATURES WORKING!")
        print("\n💡 Safe to commit - no regressions detected")

if __name__ == '__main__':
    import pytest
    # Run as a pytest test (assertions + skip) when executed directly
    raise SystemExit(pytest.main([__file__, '-v']))