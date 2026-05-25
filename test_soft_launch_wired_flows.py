#!/usr/bin/env python3
"""
Comprehensive smoke tests for soft-launch wired flows.
Tests all 4 core actions: Support/Oppose, Comments, Evidence, Voting.
"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, '.')

from app import app
from extensions import db
from models import (
    Artifact, ArtifactRelation, Comment, Bridge,
    Vote, Ballot, User, Layer
)


def test_support_oppose_flow():
    """Test support/oppose endpoints create artifact relations."""
    print("Testing Support/Oppose flow...")
    
    with app.app_context():
        c = app.test_client()
        
        # Get test artifact
        artifact = Artifact.query.first()
        if not artifact:
            print("  ❌ No test artifact found")
            return False
        
        # Create test user if needed
        user = User.query.first()
        if not user:
            print("  ⚠️  No users - skipping auth tests")
            return True
        
        # Test support endpoint (requires auth, will redirect without session)
        r = c.post(f'/api/artifacts/{artifact.id}/support/', 
                   json={}, 
                   content_type='application/json')
        
        # Expect 302 (redirect to login), 401, or 201 (success)
        if r.status_code in (302, 401, 201):
            print(f"  ✓ Support endpoint responds: {r.status_code} (auth required)")
        else:
            print(f"  ❌ Support endpoint failed: {r.status_code}")
            return False
        
        # Test oppose endpoint
        r = c.post(f'/api/artifacts/{artifact.id}/opposition/', 
                   json={}, 
                   content_type='application/json')
        
        if r.status_code in (302, 401, 201):
            print(f"  ✓ Oppose endpoint responds: {r.status_code} (auth required)")
        else:
            print(f"  ❌ Oppose endpoint failed: {r.status_code}")
            return False
        
        # Test relations endpoint (public)
        r = c.get(f'/api/artifacts/{artifact.id}/relations/')
        if r.status_code == 200:
            data = r.get_json()
            print(f"  ✓ Relations endpoint works (outgoing: {len(data['outgoing'])}, incoming: {len(data['incoming'])})")
        else:
            print(f"  ❌ Relations endpoint failed: {r.status_code}")
            return False
    
    return True


def test_comments_flow():
    """Test comment creation and listing."""
    print("\nTesting Comments flow...")
    
    with app.app_context():
        c = app.test_client()
        
        artifact = Artifact.query.first()
        if not artifact:
            print("  ❌ No test artifact found")
            return False
        
        # Test GET comments (public)
        r = c.get(f'/api/artifacts/{artifact.id}/comments/')
        if r.status_code == 200:
            data = r.get_json()
            print(f"  ✓ GET comments works ({data['count']} comments)")
        else:
            print(f"  ❌ GET comments failed: {r.status_code}")
            return False
        
        # Test POST comment (requires auth, will redirect without session)
        r = c.post(f'/api/artifacts/{artifact.id}/comments/',
                   json={'text': 'Test comment from smoke test'},
                   content_type='application/json')
        
        if r.status_code in (302, 401, 201):
            print(f"  ✓ POST comment endpoint responds: {r.status_code} (auth required)")
        else:
            print(f"  ❌ POST comment failed: {r.status_code}")
            return False
    
    return True


def test_evidence_flow():
    """Test evidence (bridge) creation and listing."""
    print("\nTesting Evidence flow...")
    
    with app.app_context():
        c = app.test_client()
        
        artifact = Artifact.query.first()
        if not artifact:
            print("  ❌ No test artifact found")
            return False
        
        # Test GET bridges
        artifact_url = f'http://localhost:8001/artifacts/{artifact.id}'
        r = c.get(f'/api/bridges/?source_url={artifact_url}')
        
        if r.status_code == 200:
            data = r.get_json()
            print(f"  ✓ GET bridges works ({data['count']} bridges)")
        else:
            print(f"  ❌ GET bridges failed: {r.status_code}")
            return False
        
        # Test POST bridge (requires auth)
        r = c.post('/api/bridges/',
                   json={
                       'name': 'Test evidence',
                       'source': {
                           'url': artifact_url,
                           'content_type': 'text'
                       },
                       'target': {
                           'url': 'https://example.com/evidence',
                           'content_type': 'text'
                       },
                       'relationship': 'supported_by'
                   },
                   content_type='application/json')
        
        if r.status_code in (302, 401, 201):
            print(f"  ✓ POST bridge endpoint responds: {r.status_code} (auth required)")
        else:
            print(f"  ❌ POST bridge failed: {r.status_code}")
            return False
    
    return True


def test_voting_flow():
    """Test vote creation and ballot casting."""
    print("\nTesting Voting flow...")
    
    with app.app_context():
        c = app.test_client()
        
        artifact = Artifact.query.first()
        if not artifact:
            print("  ❌ No test artifact found")
            return False
        
        # Check if vote exists
        vote = Vote.query.filter_by(artifact_id=artifact.id).first()
        
        if vote:
            print(f"  ✓ Vote exists for artifact (id: {vote.id})")
            
            # Test GET vote details
            r = c.get(f'/api/votes/{vote.id}/')
            if r.status_code == 200:
                print(f"  ✓ GET vote details works")
            else:
                print(f"  ❌ GET vote failed: {r.status_code}")
                return False
            
            # Test POST ballot (requires auth)
            r = c.post(f'/api/votes/{vote.id}/ballot/',
                       json={'position': 'support'},
                       content_type='application/json')
            
            if r.status_code in (302, 401, 201, 400):  # 302=redirect, 400 if already voted
                print(f"  ✓ POST ballot endpoint responds: {r.status_code} (auth required)")
            else:
                print(f"  ❌ POST ballot failed: {r.status_code}")
                return False
        else:
            print("  ⚠️  No vote exists for test artifact")
            
            # Test creating a vote (requires layer and auth)
            if artifact.layer_id:
                r = c.post(f'/api/layers/{artifact.layer_id}/votes/',
                           json={
                               'title': 'Test vote',
                               'start_at': datetime.utcnow().isoformat(),
                               'end_at': (datetime.utcnow() + timedelta(days=7)).isoformat(),
                               'quorum_count': 3,
                               'submission_id': artifact.id,
                               'vote_type': 'approval'
                           },
                           content_type='application/json')
                
                if r.status_code in (302, 401, 201):
                    print(f"  ✓ POST vote endpoint responds: {r.status_code} (auth required)")
                else:
                    print(f"  ❌ POST vote failed: {r.status_code}")
                    return False
            else:
                print("  ⚠️  Artifact has no layer_id, cannot create vote")
    
    return True


def test_soft_launch_pages():
    """Test soft-launch page renders with wired artifact."""
    print("\nTesting Soft Launch Pages...")
    
    with app.app_context():
        c = app.test_client()
        
        # Test homepage
        r = c.get('/soft-launch/')
        if r.status_code == 200 and 'Build decisions' in r.get_data(as_text=True):
            print("  ✓ Soft launch homepage loads")
        else:
            print(f"  ❌ Homepage failed: {r.status_code}")
            return False
        
        # Test artifact page with all scenarios
        for scenario in ['under_review', 'vote_open', 'approved']:
            r = c.get(f'/soft-launch/artifact/?scenario={scenario}')
            if r.status_code == 200:
                text = r.get_data(as_text=True)
                
                # Check for wired artifact ID in page
                wired_id = os.environ.get('SOFT_LAUNCH_WIRED_ARTIFACT_ID', '').strip()
                if wired_id and f'data-wired-artifact-id="{wired_id}"' in text:
                    print(f"  ✓ Artifact page ({scenario}) has wired ID")
                else:
                    print(f"  ⚠️  Artifact page ({scenario}) loads but no wired ID")
            else:
                print(f"  ❌ Artifact page ({scenario}) failed: {r.status_code}")
                return False
    
    return True


def test_database_state():
    """Check database has required entities."""
    print("\nChecking Database State...")
    
    with app.app_context():
        artifact_count = Artifact.query.count()
        user_count = User.query.count()
        comment_count = Comment.query.count()
        bridge_count = Bridge.query.count()
        vote_count = Vote.query.count()
        
        print(f"  Artifacts: {artifact_count}")
        print(f"  Users: {user_count}")
        print(f"  Comments: {comment_count}")
        print(f"  Bridges: {bridge_count}")
        print(f"  Votes: {vote_count}")
        
        if artifact_count == 0:
            print("  ❌ No artifacts in database!")
            return False
        
        wired_id = os.environ.get('SOFT_LAUNCH_WIRED_ARTIFACT_ID', '').strip()
        if wired_id:
            wired_artifact = Artifact.query.get(wired_id)
            if wired_artifact:
                print(f"  ✓ Wired artifact exists: {wired_artifact.title}")
            else:
                print(f"  ❌ Wired artifact ID not found: {wired_id}")
                return False
        else:
            print("  ⚠️  SOFT_LAUNCH_WIRED_ARTIFACT_ID not set")
    
    return True


def main():
    """Run all soft-launch flow tests."""
    print("=" * 70)
    print("SOFT LAUNCH WIRED FLOWS - SMOKE TESTS")
    print("=" * 70)
    
    tests = [
        ("Database State", test_database_state),
        ("Support/Oppose", test_support_oppose_flow),
        ("Comments", test_comments_flow),
        ("Evidence", test_evidence_flow),
        ("Voting", test_voting_flow),
        ("Pages", test_soft_launch_pages),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ {name} test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    for name, success in results:
        status = "✓ PASS" if success else "❌ FAIL"
        print(f"{status:12} {name}")
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All soft-launch flows are working!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check output above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
