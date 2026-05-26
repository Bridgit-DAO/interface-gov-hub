"""Tests for workgroup URL/document link helpers."""
from services.groups import extract_dp_number, dp_image_url
from services.workgroup_links import extract_dp_number_from_title, workgroup_display_sort_key


def test_extract_dp_number():
    assert extract_dp_number('dp1-federated-auth') == 1
    assert extract_dp_number('dp21-multi-modal') == 21
    assert extract_dp_number('dp22---epistemic-continuity-digital-artifacts') == 22


def test_dp_image_url():
    assert dp_image_url(1) == '/static/images/dp/dp1.png'
    assert dp_image_url(22) == '/static/images/dp/dp22.png'
    assert dp_image_url(99) is None


def test_workgroup_display_sort_key():
    class _Wg:
        def __init__(self, acronym, name=''):
            self.acronym = acronym
            self.name = name

    items = [
        _Wg('dp10-education', 'DP10 - Education'),
        _Wg('dp2-agency', 'DP2 - Participant Agency'),
        _Wg('dp22---epistemic', 'DP22 - Civic Memory'),
        _Wg('ml-governance', 'ML Governance'),
    ]
    ordered = [wg.acronym for wg in sorted(items, key=workgroup_display_sort_key)]
    assert ordered.index('dp2-agency') < ordered.index('dp10-education')
    assert ordered.index('dp10-education') < ordered.index('dp22---epistemic')
    assert ordered[-1] == 'ml-governance'


def test_workgroup_select_options_html():
    import html as html_mod
    from app import app
    from models import Workgroup
    from services.workgroup_links import workgroup_select_options_html, workgroup_belongs_to_layer

    with app.app_context():
        wg = Workgroup.query.filter(Workgroup.acronym.like('dp%')).first()
        if not wg:
            print('⚠️  No DP workgroup — skip')
            return
        options = workgroup_select_options_html(wg.layer_id, wg.acronym)
        assert wg.acronym in options
        assert html_mod.escape(wg.name or wg.acronym) in options
        assert workgroup_belongs_to_layer(wg.acronym, wg.layer_id)
        assert not workgroup_belongs_to_layer('ml-governance', wg.layer_id)


def test_dp_workgroups_available_on_overweb():
    from app import create_app
    from models import Layer, Workgroup
    from services.workgroup_links import is_dp_workgroup, query_workgroups_for_layer

    app = create_app()
    with app.app_context():
        overweb = Layer.query.filter_by(slug='the-overweb').first()
        metaweb = Layer.query.filter_by(slug='the-metaweb').first()
        if not overweb or not metaweb:
            return
        dp_on_metaweb = [
            wg for wg in Workgroup.query.filter_by(layer_id=metaweb.id, status='active').all()
            if is_dp_workgroup(wg)
        ]
        if not dp_on_metaweb:
            return
        overweb_wgs = query_workgroups_for_layer(overweb.id, status='active')
        overweb_acronyms = {wg.acronym for wg in overweb_wgs}
        for wg in dp_on_metaweb:
            assert wg.acronym in overweb_acronyms, f'{wg.acronym} missing on Overweb'


def test_query_workgroups_for_layer_dedupes():
    """Primary + secondary links must not return the same workgroup twice."""
    from app import create_app
    from models import Layer
    from services.workgroup_links import query_workgroups_for_layer

    app = create_app()
    with app.app_context():
        overweb = Layer.query.filter_by(slug='the-overweb').first()
        if not overweb:
            return
        rows = query_workgroups_for_layer(overweb.id, status='active')
        ids = [wg.id for wg in rows]
        assert len(ids) == len(set(ids)), 'duplicate workgroup ids in layer query'


def test_overweb_workgroups_api_when_layer_feature_off():
    """GET /api/layers/<overweb>/workgroups/ works via secondary links even if workgroups off."""
    from app import create_app
    from models import Layer, Workgroup
    from services.workgroup_links import is_dp_workgroup, query_workgroups_for_layer

    app = create_app()
    with app.app_context():
        overweb = Layer.query.filter_by(slug='the-overweb').first()
        if not overweb:
            return
        expected = query_workgroups_for_layer(overweb.id, status='active')
        if not expected:
            return
        with app.test_client() as client:
            resp = client.get(f'/api/layers/{overweb.id}/workgroups/?status=active')
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['count'] == len(expected)
            for row in data['workgroups']:
                wg = Workgroup.query.filter_by(acronym=row['acronym']).first()
                assert wg and is_dp_workgroup(wg)


def test_extract_dp_number_from_title():
    assert extract_dp_number_from_title('DP1 - Federated Auth') == 1
    assert extract_dp_number_from_title('DP13 – AI Containment') == 13
    assert extract_dp_number_from_title('DP1: Federated Auth') == 1
    assert extract_dp_number_from_title('DP19 - Amplifying') == 19
    assert extract_dp_number_from_title('Not DP1') is None
    assert extract_dp_number_from_title('') is None


def test_resolve_document_workgroup_meta_empty():
    from services.workgroup_links import resolve_document_workgroup_meta

    empty_index = {'by_acronym': {}, 'by_draft_ref': {}, 'by_dp_num': {}}
    meta = resolve_document_workgroup_meta(
        group='N/A',
        title='Unrelated doc',
        index=empty_index,
    )
    assert meta['workgroup_name'] is None
    assert meta['workgroup_href'] is None


def test_resolve_document_workgroup_meta_by_dp_title():
    from app import app
    from models import Workgroup
    from services.workgroup_links import resolve_document_workgroup_meta

    with app.app_context():
        wg = Workgroup.query.filter(Workgroup.acronym.like('dp%')).first()
        if not wg:
            print('⚠️  No DP workgroup — skip')
            return
        dp = extract_dp_number(wg.acronym or '')
        if dp is None:
            return
        meta = resolve_document_workgroup_meta(
            name='fake-id',
            title=f'DP{dp} - Example',
        )
        assert meta.get('workgroup_href'), meta
        assert meta.get('workgroup_name')
