"""Layers API: layer CRUD, admins, activity, members, email-recipients, send-email."""
import json
import os
from datetime import datetime

from flask import Blueprint, jsonify, request, abort, current_app
from sqlalchemy import func, or_, not_

from extensions import db
from models import (
    Layer, LayerMember, LayerAdmin, Workgroup, User, EventLog, StatusChange,
    Waitlist, WaitlistEntry, WaitlistEmailSignup, WorkingGroupMember,
    Claim, EmailUnsubscribe, Submission, Role, Quest, Artifact, ArtifactRelation,
    Guild, GuildLayerLink,
)
from services.access_policy import (
    layer_listing_visible,
    normalize_join_policy_layer_guild,
    normalize_listing_visibility,
)
from services.identity import get_current_user, require_auth
from services.coordination import is_layer_admin
from services.events import emit_event
from services.utils import create_slug
from services.ordinals import fetch_meta_domain_from_inscription
from services.knowledge_layer import KNOWLEDGE_FORM_VALUES, canonical_knowledge_form
from services.layer_features import (
    LAYER_FEATURE_ORDER,
    get_effective_features,
    layer_enabled_features_to_json,
    validate_layer_features_patch,
)
from services.event_registry import EXCLUDED_FROM_ACTIVITY_FEED
from services.referral_tokens import attribution_from_token
from services.layer_prefixes import (
    list_prefixes as _svc_list_prefixes,
    get_default_prefix as _svc_get_default_prefix,
    add_prefix as _svc_add_prefix,
    update_prefix as _svc_update_prefix,
    delete_prefix as _svc_delete_prefix,
    set_default_prefix as _svc_set_default_prefix,
    prefixes_for_user as _svc_prefixes_for_user,
    is_valid_prefix_format as _svc_is_valid_prefix_format,
    normalize_display_status as _svc_normalize_display_status,
    PUBLIC_LAYER_ADMIN_ALLOWED_STATUSES as _PUBLIC_DS_STATUSES,
)

bp = Blueprint('layers', __name__, url_prefix='/api/layers')

# Omit from default layer activity API; include via ?event_type= (see services/event_registry.py)
ACTIVITY_FEED_EXCLUDED_EVENT_TYPES = EXCLUDED_FROM_ACTIVITY_FEED


def _ref_token_allows_layer_detail(project) -> bool:
    """Allow a scoped referral token to open the private layer landing page it targets."""
    ref_token = (request.args.get('ref_token') or '').strip()
    if not ref_token:
        return False
    attr = attribution_from_token(ref_token)
    if not attr or not attr.get('valid') or attr.get('product') != 'gov_hub':
        return False
    if attr.get('scope_type') == 'layer' and attr.get('scope_id') == project.id:
        return True
    if attr.get('entity_type') == 'layer' and attr.get('entity_id') == project.id:
        return True
    if attr.get('scope_type') == 'waitlist' or attr.get('entity_type') == 'waitlist':
        waitlist_id = attr.get('scope_id') if attr.get('scope_type') == 'waitlist' else attr.get('entity_id')
        waitlist = Waitlist.query.get(waitlist_id) if waitlist_id else None
        return bool(waitlist and waitlist.layer_id == project.id)
    return False


@bp.route('/', methods=['GET'])
def list_layers():
    """List all projects with filtering."""
    status = request.args.get('status')
    approval_status = request.args.get('approval_status')
    display_status = request.args.get('display_status')

    query = Layer.query
    if status:
        query = query.filter_by(status=status)
    if approval_status:
        query = query.filter_by(approval_status=approval_status)
    if display_status:
        query = query.filter_by(display_status=display_status)

    # Hide imported auth shells from default directory (Revised Option C).
    # Use OR-of-negations so NULL layer_kind/stewardship (standard layers) stay visible in SQLite.
    if request.args.get('include_auth_imports') != '1':
        query = query.filter(
            db.or_(
                Layer.layer_kind.is_(None),
                Layer.layer_kind != 'auth_community',
                Layer.stewardship.is_(None),
                Layer.stewardship != 'unmanaged',
            )
        )

    query = query.order_by(Layer.last_activity.desc())
    layers = query.all()
    viewer = get_current_user()

    # Layer admins still see their own pending layers (so they can iterate
    # during setup before flipping visibility to ``active``).
    from services.layer_prefixes import _layer_admin_layer_ids
    admin_layer_ids = set(_layer_admin_layer_ids((viewer or {}).get('id')))

    filtered = []
    for p in layers:
        if not layer_listing_visible(p, viewer):
            continue
        ds = getattr(p, 'display_status', 'pending') or 'pending'
        if ds == 'active':
            filtered.append(p)
        elif p.id in admin_layer_ids and ds in _PUBLIC_DS_STATUSES:
            filtered.append(p)
        elif display_status == ds:
            # Caller explicitly asked for a specific display_status (e.g. the
            # admin pages pass display_status='pending' to review the queue).
            filtered.append(p)
    layers = filtered

    layer_ids = [p.id for p in layers]
    count_map = {}
    if layer_ids:
        rows = db.session.query(Workgroup.layer_id, func.count(Workgroup.id)).filter(
            Workgroup.layer_id.in_(layer_ids)
        ).group_by(Workgroup.layer_id).all()
        count_map = {lid: c for lid, c in rows}

    result = []
    for p in layers:
        d = p.to_dict()
        d['workgroups_count'] = count_map.get(p.id, 0)
        result.append(d)

    resp = jsonify({'layers': result, 'count': len(result)})
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return resp


@bp.route('/', methods=['POST'])
@require_auth
def create_layer():
    """Create a new project."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json() or {}
    name = data.get('name', '').strip()
    mission = data.get('mission') or data.get('mission_statement') or ''
    mission = mission.strip() if mission else None
    description = data.get('description', '').strip()

    if not name:
        return jsonify({'error': 'Layer name is required'}), 400

    existing = Layer.query.filter_by(name=name).first()
    if existing:
        return jsonify({'error': 'Layer name already exists'}), 400

    slug = create_slug(name)
    reserved = current_app.config.get('RESERVED_SUBDOMAINS', set())
    if slug in reserved:
        return jsonify({'error': f'The slug "{slug}" is reserved and cannot be used. Please choose a different project name.'}), 400

    counter = 1
    original_slug = slug
    while Layer.query.filter_by(slug=slug).first():
        slug = f"{original_slug}-{counter}"
        counter += 1
        if slug in reserved:
            counter += 1
            slug = f"{original_slug}-{counter}"

    layer = Layer(
        name=name,
        slug=slug,
        initiator_id=current_user['id'],
        mission=mission or None,
        description=description,
        status='proposed',
        approval_status='pending',
        listing_visibility=normalize_listing_visibility(data.get('listing_visibility')),
        join_policy=normalize_join_policy_layer_guild(data.get('join_policy')),
    )
    from services.nft_gate import gate_has_requirements, parse_nft_gate_rules_text, save_layer_nft_gate

    jp = layer.join_policy
    if data.get('nft_gated') or data.get('join_policy') == 'nft_gated':
        layer.join_policy = 'nft_gated'
        jp = 'nft_gated'
    if jp == 'nft_gated':
        rules = data.get('nft_gate_rules') or ''
        gate = data.get('nft_gate') if isinstance(data.get('nft_gate'), dict) else parse_nft_gate_rules_text(rules)
        if not gate_has_requirements(gate):
            return jsonify({'error': 'NFT-gated layers require at least one allowed NFT rule'}), 400
        save_layer_nft_gate(layer, gate)
    db.session.add(layer)
    db.session.commit()

    return jsonify({'success': True, 'layer': layer.to_dict()}), 201


@bp.route('/by-slug/<slug>/', methods=['GET'])
def get_layer_by_slug(slug):
    """Get project details by slug."""
    current_app.logger.info(f"[LAYER] api_get_project_by_slug called: slug={slug!r}")
    project = Layer.query.filter_by(slug=slug).first()
    if not project:
        current_app.logger.warning(f"[LAYER] api_get_project_by_slug: no project found for slug={slug!r}")
        abort(404)
    current_app.logger.info(f"[LAYER] api_get_project_by_slug: found project id={project.id} name={project.name}")
    current_user = get_current_user()
    if not layer_listing_visible(project, current_user) and not _ref_token_allows_layer_detail(project):
        abort(404)
    workgroups_count = Workgroup.query.filter_by(layer_id=project.id).count()
    project_dict = project.to_dict()
    project_dict['workgroups_count'] = workgroups_count
    project_dict['effective_features'] = {
        k: get_effective_features(project).get(k, True) for k in LAYER_FEATURE_ORDER
    }
    if current_user:
        member = LayerMember.query.filter_by(
            layer_id=project.id, user_id=current_user['id'], status='active'
        ).first()
        project_dict['is_member'] = member is not None
        project_dict['member_role'] = member.role if member else None
    else:
        project_dict['is_member'] = False
        project_dict['member_role'] = None
    return jsonify(project_dict)


@bp.route('/<layer_id>/', methods=['GET'])
def get_layer(layer_id):
    """Get project details by id or slug."""
    current_app.logger.info(f"[LAYER] api_get_layer called: layer_id={layer_id!r}")
    project = Layer.query.get(layer_id)
    if not project:
        project = Layer.query.filter_by(slug=layer_id).first()
    if not project:
        current_app.logger.warning(f"[LAYER] api_get_layer: no layer for id/slug={layer_id!r}")
        abort(404)
    current_app.logger.info(f"[LAYER] api_get_project: found id={project.id} slug={project.slug}")

    current_user = get_current_user()
    if not layer_listing_visible(project, current_user) and not _ref_token_allows_layer_detail(project):
        abort(404)

    workgroups_count = Workgroup.query.filter_by(layer_id=project.id).count()
    project_dict = project.to_dict()
    project_dict['workgroups_count'] = workgroups_count
    project_dict['effective_features'] = {
        k: get_effective_features(project).get(k, True) for k in LAYER_FEATURE_ORDER
    }
    if current_user:
        member = LayerMember.query.filter_by(
            layer_id=project.id, user_id=current_user['id'], status='active'
        ).first()
        project_dict['is_member'] = member is not None
        project_dict['member_role'] = member.role if member else None
    else:
        project_dict['is_member'] = False
        project_dict['member_role'] = None

    return jsonify(project_dict)


@bp.route('/<layer_id>/carousel/', methods=['GET'])
def layer_carousel(layer_id):
    """Get carousel items for a layer. Combines auto items (drafts, roles, opportunities) and custom items."""
    project = Layer.query.get_or_404(layer_id)
    if not project:
        project = Layer.query.filter_by(slug=layer_id).first()
    if not project:
        abort(404)
    if not layer_listing_visible(project, get_current_user()):
        abort(404)

    config = {}
    if project.carousel_config:
        try:
            config = json.loads(project.carousel_config)
        except (json.JSONDecodeError, TypeError):
            pass

    eff = get_effective_features(project)
    auto = config.get('auto_items') or {}
    recent_drafts = auto.get('recent_drafts', True) and eff.get('docs', True)
    open_roles = auto.get('open_roles', True) and eff.get('roles', True)
    open_opportunities = auto.get('open_opportunities', True) and eff.get('opportunities', True)

    items = []
    layer_slug = project.slug

    try:
        if recent_drafts:
            subs = Submission.query.filter(
                Submission.layer_id == project.id,
                Submission.status.in_(['approved', 'submitted']),
                Submission.doc_type == 'draft'
            ).order_by(Submission.submitted_at.desc().nullslast()).limit(5).all()
            for s in subs:
                items.append({
                    'type': 'draft',
                    'title': s.title or s.draft_name or 'Untitled',
                    'description': (s.abstract or '')[:500] if s.abstract else None,
                    'draft_id': s.draft_name or str(s.id),
                    'image': None,
                    'link': f'/doc/draft/{s.draft_name or s.id}/',
                })
    except Exception:
        pass

    try:
        if open_roles:
            roles = Role.query.filter_by(layer_id=project.id, status='approved').all()
            active_claims = {c.role_id for c in Claim.query.filter_by(layer_id=project.id, status='active').all()}
            count = 0
            for r in roles:
                if r.id not in active_claims and count < 5:
                    items.append({
                        'type': 'role',
                        'title': r.title_guild or r.title_operational or 'Role',
                        'description': (r.description or '')[:300] if r.description else None,
                        'image': r.image_url,
                        'link': f'/layer/{layer_slug}/roles/{r.role_slug}/',
                    })
                    count += 1
    except Exception:
        pass

    try:
        if open_opportunities:
            opp_resp = _layer_opportunities_data(project.id, eff)
            if eff.get('quests', True):
                for q in (opp_resp.get('open_quests') or [])[:3]:
                    items.append({
                        'type': 'opportunity',
                        'title': q.get('title') or 'Open Quest',
                        'description': q.get('description'),
                        'image': None,
                        'link': f'/layers/{layer_slug}/quests/{q.get("id")}/',
                    })
            for a in (opp_resp.get('missing_support') or [])[:2]:
                items.append({
                    'type': 'opportunity',
                    'title': (a.get('title') or 'Draft') + ' (needs support)',
                    'description': a.get('description'),
                    'image': None,
                    'link': f'/layers/{layer_slug}/artifacts/{a.get("id")}/' if a.get('id') else f'/doc/draft/{a.get("draft_id", "")}/',
                })
    except Exception:
        pass

    custom = config.get('custom_items') or []
    for c in custom:
        if c.get('title'):
            items.append({
                'type': 'custom',
                'title': c.get('title', ''),
                'description': c.get('description'),
                'image': c.get('image'),
                'link': c.get('link'),
            })

    return jsonify({'items': items[:12]})


def _layer_opportunities_data(layer_id, effective=None):
    """Helper: opportunities data for carousel."""
    if effective is None:
        layer = Layer.query.get(layer_id)
        effective = get_effective_features(layer)
    artifacts = Artifact.query.filter_by(layer_id=layer_id, artifact_type='submission').all()
    missing_support = []
    for a in artifacts:
        incoming = ArtifactRelation.query.filter(
            ArtifactRelation.to_object_type == 'artifact',
            ArtifactRelation.to_object_id == a.id,
        ).all()
        has_support = any(r.relation_type == 'supports' for r in incoming)
        if not has_support:
            sub = Submission.query.filter_by(artifact_id=a.id).first()
            draft_id = sub.id if sub else a.id
            abstract = (sub.abstract or '')[:500] if sub and sub.abstract else None
            missing_support.append({
                'id': a.id, 'title': a.title or 'Untitled', 'draft_id': draft_id,
                'description': abstract,
            })
    open_quests = []
    if effective.get('quests', True):
        for q in Quest.query.filter_by(layer_id=layer_id, status='open').order_by(Quest.created_at.desc()).limit(5):
            open_quests.append({
                'id': q.id,
                'title': q.title,
                'description': (q.description or '')[:300] if q.description else None,
            })
    return {'missing_support': missing_support, 'open_quests': open_quests}


@bp.route('/<layer_id>/', methods=['PATCH'])
@require_auth
def update_layer(layer_id):
    """Update project details."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    project = Layer.query.get_or_404(layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Permission denied'}), 403

    data = request.get_json()

    if 'name' in data:
        name = (data['name'] or '').strip()
        if not name:
            return jsonify({'error': 'Layer name cannot be empty'}), 400
        if name != project.name:
            if Layer.query.filter_by(name=name).first():
                return jsonify({'error': 'A project with this name already exists'}), 400
            project.name = name
            slug = create_slug(name)
            original_slug = slug
            counter = 1
            while Layer.query.filter(Layer.slug == slug, Layer.id != layer_id).first():
                slug = f'{original_slug}-{counter}'
                counter += 1
            project.slug = slug
    if 'mission' in data:
        project.mission = data['mission'] if data['mission'] else None
    if 'description' in data:
        project.description = data['description']
    if 'about_content' in data:
        project.about_content = data['about_content'] if data['about_content'] else None
    if 'carousel_config' in data:
        val = data['carousel_config']
        project.carousel_config = json.dumps(val) if val is not None else None
    if 'image_url' in data:
        raw_img = data.get('image_url')
        if raw_img is None or (isinstance(raw_img, str) and not raw_img.strip()):
            project.image_url = None
        elif isinstance(raw_img, str):
            project.image_url = raw_img.strip()
        else:
            return jsonify({'error': 'image_url must be a string or null'}), 400
    if 'status' in data and data['status'] in ['proposed', 'active', 'stabilizing', 'maintaining', 'dormant', 'concluded', 'archived']:
        old_status = project.status
        project.status = data['status']
        if old_status != project.status:
            status_change = StatusChange(
                entity_type='project',
                entity_id=layer_id,
                field_name='status',
                from_value=old_status,
                to_value=project.status,
                note=data.get('status_reason'),
                changed_by_id=current_user['id']
            )
            db.session.add(status_change)
    if 'status_reason' in data:
        project.status_reason = data['status_reason']
    if 'meta_domain_inscription_id' in data:
        val = (data['meta_domain_inscription_id'] or '').strip()
        project.meta_domain_inscription_id = val if val else None
        if val:
            domain = fetch_meta_domain_from_inscription(val)
            project.meta_domain = domain
        else:
            project.meta_domain = None
    if 'listing_visibility' in data:
        new_vis = normalize_listing_visibility(data.get('listing_visibility'))
        current_vis = getattr(project, 'listing_visibility', None) or 'public'
        if current_vis == 'public' and new_vis == 'private':
            return jsonify({
                'error': 'Layers cannot be made private after they are public. Set visibility when creating the layer.',
            }), 400
        if current_vis == 'private' and new_vis == 'public':
            project.listing_visibility = 'public'
    if 'display_status' in data:
        project.display_status = _svc_normalize_display_status(data.get('display_status'))
    if 'join_policy' in data:
        project.join_policy = normalize_join_policy_layer_guild(data.get('join_policy'))
    if 'nft_gate_rules' in data or 'nft_gate' in data:
        from services.nft_gate import (
            gate_has_requirements,
            parse_nft_gate_rules_text,
            save_layer_nft_gate,
        )

        if 'nft_gate' in data and isinstance(data.get('nft_gate'), dict):
            gate = data['nft_gate']
        else:
            gate = parse_nft_gate_rules_text(data.get('nft_gate_rules') or '')
        if getattr(project, 'join_policy', None) == 'nft_gated' and not gate_has_requirements(gate):
            return jsonify({'error': 'Add at least one NFT allow-list rule for this layer'}), 400
        save_layer_nft_gate(project, gate)
    if 'enabled_features' in data:
        raw_ef = data['enabled_features']
        if raw_ef is None:
            project.enabled_features = None
        else:
            from services.product_rollout import get_rollout_config

            overrides, err = validate_layer_features_patch(raw_ef, global_cfg=get_rollout_config())
            if err:
                return jsonify({'error': err}), 400
            # Persist only explicit false overrides (null layer config = all on)
            stored = {k: v for k, v in overrides.items() if v is False}
            project.enabled_features = layer_enabled_features_to_json(stored)

    if 'nav_pill_config' in data:
        from services.nav_pills import validate_layer_nav_pill_patch

        raw_npc = data['nav_pill_config']
        if raw_npc is None:
            project.nav_pill_config = None
        else:
            normalized, err = validate_layer_nav_pill_patch(raw_npc)
            if err:
                return jsonify({'error': err}), 400
            project.nav_pill_config = json.dumps(normalized, sort_keys=True) if normalized else None

    project.updated_at = datetime.utcnow()
    if data:
        emit_event('layer_config_changed', actor_type='user', actor_id=current_user['id'],
                   subject_type='layer', subject_id=layer_id, layer_id=layer_id,
                   payload={'updated_fields': list(data.keys())})
    db.session.commit()

    if getattr(project, 'canopi_meta_community_id', None) or getattr(project, 'approval_status', None) == 'approved':
        from services.canopi_community_sync import provision_or_sync_layer

        provision_or_sync_layer(project, force=bool(getattr(project, 'canopi_meta_community_id', None)))

    out = project.to_dict()
    out['effective_features'] = {
        k: get_effective_features(project).get(k, True) for k in LAYER_FEATURE_ORDER
    }
    return jsonify({'success': True, 'project': out})


@bp.route('/<layer_id>/approve/', methods=['POST'])
@require_auth
def approve_layer(layer_id):
    """Approve or reject a project (admin only)."""
    current_user = get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    project = Layer.query.get_or_404(layer_id)
    data = request.get_json()
    action = data.get('action')

    if action not in ['approve', 'reject']:
        return jsonify({'error': 'Invalid action. Must be approve or reject.'}), 400

    old_status = project.approval_status
    project.approval_status = 'approved' if action == 'approve' else 'rejected'
    project.approved_by_id = current_user['id']
    project.approved_at = datetime.utcnow()

    status_change = StatusChange(
        entity_type='project',
        entity_id=layer_id,
        field_name='approval_status',
        from_value=old_status,
        to_value=project.approval_status,
        note=data.get('note'),
        changed_by_id=current_user['id']
    )
    db.session.add(status_change)

    if action == 'approve' and project.status == 'proposed':
        old_op_status = project.status
        project.status = 'active'
        db.session.add(StatusChange(
            entity_type='project',
            entity_id=layer_id,
            field_name='status',
            from_value=old_op_status,
            to_value='active',
            note='Auto-activated on site admin approval',
            changed_by_id=current_user['id']
        ))

    db.session.commit()

    if action == 'approve':
        from services.canopi_community_sync import provision_or_sync_layer

        provision_or_sync_layer(project, force=True)

    return jsonify({'success': True, 'project': project.to_dict()})


@bp.route('/<layer_id>/admins/', methods=['GET'])
def list_layer_admins(layer_id):
    """List project admins (owner + assigned). Only project admins can see this."""
    project = Layer.query.get_or_404(layer_id)
    current_user = get_current_user()
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project admins can view the admin list'}), 403

    owner = project.initiator
    owner_dict = {
        'user_id': owner.id,
        'username': owner.username,
        'display_name': owner.displayName or owner.username,
        'is_owner': True,
        'added_at': project.created_at.isoformat() if project.created_at else None
    }

    assigned = LayerAdmin.query.filter_by(layer_id=layer_id).all()
    assigned_list = []
    for pa in assigned:
        u = pa.user
        assigned_list.append({
            'user_id': u.id,
            'username': u.username,
            'display_name': u.displayName or u.username,
            'is_owner': False,
            'added_at': pa.added_at.isoformat() if pa.added_at else None
        })

    return jsonify({
        'owner': owner_dict,
        'admins': assigned_list,
        'count': 1 + len(assigned_list)
    })


@bp.route('/<layer_id>/admins/', methods=['POST'])
@require_auth
def add_layer_admin(layer_id):
    """Add a project admin. Only existing project admins can add."""
    project = Layer.query.get_or_404(layer_id)
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project admins can add admins'}), 403

    data = request.get_json()
    user_id = data.get('user_id')
    username = data.get('username')

    if user_id is not None:
        user_id = str(user_id)
    elif username:
        u = User.query.filter_by(username=username).first()
        if not u:
            return jsonify({'error': 'User not found'}), 404
        user_id = u.id
    else:
        return jsonify({'error': 'Provide user_id or username'}), 400

    if user_id == project.initiator_id:
        return jsonify({'error': 'Owner is already an admin'}), 400

    existing = LayerAdmin.query.filter_by(layer_id=layer_id, user_id=user_id).first()
    if existing:
        return jsonify({'error': 'User is already a project admin'}), 400

    pa = LayerAdmin(layer_id=layer_id, user_id=user_id)
    db.session.add(pa)
    db.session.commit()

    u = User.query.get(user_id)
    return jsonify({
        'success': True,
        'admin': {
            'user_id': u.id,
            'username': u.username,
            'display_name': u.displayName or u.username,
            'is_owner': False,
            'added_at': pa.added_at.isoformat() if pa.added_at else None
        }
    })


@bp.route('/<layer_id>/admins/<user_id>/', methods=['DELETE'])
@require_auth
def remove_layer_admin(layer_id, user_id):
    """Remove a project admin. Owner cannot be removed."""
    project = Layer.query.get_or_404(layer_id)
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project admins can remove admins'}), 403

    if user_id == project.initiator_id:
        return jsonify({'error': 'Cannot remove the layer owner'}), 400

    pa = LayerAdmin.query.filter_by(layer_id=layer_id, user_id=user_id).first()
    if not pa:
        return jsonify({'error': 'User is not an assigned admin'}), 404

    db.session.delete(pa)
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/<layer_id>/activity', methods=['GET'])
@bp.route('/<layer_id>/activity/', methods=['GET'])
def layer_activity(layer_id):
    """Layer-scoped activity feed from EventLog."""
    project = Layer.query.get(layer_id)
    if not project:
        project = Layer.query.filter_by(slug=layer_id).first()
    if not project:
        abort(404)
    resolved_id = project.id
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))
    event_types = request.args.getlist('event_type')
    query = EventLog.query.filter_by(layer_id=resolved_id)
    if event_types:
        query = query.filter(EventLog.event_type.in_(event_types))
    else:
        query = query.filter(not_(EventLog.event_type.in_(ACTIVITY_FEED_EXCLUDED_EVENT_TYPES)))
    events = query.order_by(EventLog.created_at.desc()).offset(offset).limit(limit).all()
    actor_ids = {e.actor_id for e in events if e.actor_type == 'user' and e.actor_id}
    users = {}
    ids_list = [str(x) for x in actor_ids if x and (len(str(x)) == 36 and '-' in str(x) or str(x).isdigit())]
    if ids_list:
        for u in User.query.filter(User.id.in_(ids_list)).all():
            users[str(u.id)] = u.displayName or u.username or f'User {u.id}'
    event_list = []
    for e in events:
        ev = {
            'id': e.id,
            'event_type': e.event_type,
            'actor_type': e.actor_type,
            'actor_id': e.actor_id,
            'actor_display_name': users.get(str(e.actor_id)) if e.actor_id else None,
            'subject_type': e.subject_type,
            'subject_id': e.subject_id,
            'layer_id': e.layer_id,
            'payload': json.loads(e.payload_json) if e.payload_json else None,
            'created_at': e.created_at.isoformat() if e.created_at else None,
        }
        event_list.append(ev)
    return jsonify({
        'events': event_list,
        'count': len(events)
    }), 200


@bp.route('/<layer_id>/contribution-type-filter/', methods=['POST'])
def record_contribution_type_filter(layer_id):
    """Log contribution-type facet use on layer artifact list (analytics)."""
    if not current_app.config.get('KNOWLEDGE_CONTRIBUTION_FILTERS_ENABLED', True):
        return jsonify({'success': True, 'ignored': True}), 200
    project = Layer.query.get(layer_id)
    if not project:
        project = Layer.query.filter_by(slug=layer_id).first()
    if not project:
        abort(404)
    data = request.get_json(silent=True) or {}
    kf = data.get('knowledge_form')
    if kf is not None and kf != '':
        kf = canonical_knowledge_form(str(kf))
        if kf not in KNOWLEDGE_FORM_VALUES:
            return jsonify({'error': 'Invalid knowledge_form'}), 400
    else:
        kf = None
    user = get_current_user()
    actor_type = 'user' if user else 'anonymous'
    actor_id = user['id'] if user else None
    emit_event(
        'contribution_type_filter_applied',
        actor_type=actor_type,
        actor_id=actor_id,
        subject_type='layer',
        subject_id=str(project.id),
        layer_id=project.id,
        payload={'knowledge_form': kf, 'context': 'layer_artifacts_tab'},
    )
    db.session.commit()
    return jsonify({'success': True}), 200


def _resolve_layer_for_guild(layer_id):
    project = Layer.query.get(layer_id)
    if not project:
        project = Layer.query.filter_by(slug=layer_id).first()
    return project


@bp.route('/<layer_id>/guilds/', methods=['GET'])
def list_layer_guild_links(layer_id):
    """Guilds linked to this layer (Unified Phase I)."""
    project = _resolve_layer_for_guild(layer_id)
    if not project:
        abort(404)
    links = GuildLayerLink.query.filter_by(layer_id=project.id).all()
    out = []
    for ln in links:
        g = ln.guild
        d = ln.to_dict()
        if g:
            d['guild'] = {
                'id': g.id,
                'name': g.name,
                'slug': g.slug,
                'image_url': g.image_url,
            }
        out.append(d)
    return jsonify({'links': out, 'count': len(out)}), 200


@bp.route('/<layer_id>/guilds/', methods=['POST'])
@require_auth
def attach_guild_to_layer(layer_id):
    """Link a guild to a layer (layer admin or guild officer + layer member)."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    project = _resolve_layer_for_guild(layer_id)
    if not project:
        abort(404)
    data = request.get_json(silent=True) or {}
    gid = data.get('guild_id')
    if not gid:
        return jsonify({'error': 'guild_id required'}), 400
    guild = Guild.query.get(gid)
    if not guild:
        return jsonify({'error': 'Guild not found'}), 404
    from services.guild_phase1 import can_manage_guild_layer_link

    if not can_manage_guild_layer_link(user, guild, project):
        return jsonify({'error': 'Forbidden'}), 403
    if GuildLayerLink.query.filter_by(guild_id=guild.id, layer_id=project.id).first():
        return jsonify({'error': 'Link already exists'}), 400
    from uuid import uuid4

    link = GuildLayerLink(
        id=str(uuid4()),
        guild_id=guild.id,
        layer_id=project.id,
        created_by_user_id=user['id'],
    )
    db.session.add(link)
    emit_event(
        'guild_layer_linked',
        actor_type='user',
        actor_id=user['id'],
        subject_type='guild_layer_link',
        subject_id=link.id,
        layer_id=project.id,
        payload={
            'guild_id': guild.id,
            'guild_name': guild.name,
            'layer_id': project.id,
            'layer_slug': project.slug,
        },
    )
    db.session.commit()
    return jsonify({'success': True, 'link': link.to_dict()}), 201


@bp.route('/<layer_id>/guilds/<guild_id>/', methods=['DELETE'])
@require_auth
def detach_guild_from_layer(layer_id, guild_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    project = _resolve_layer_for_guild(layer_id)
    if not project:
        abort(404)
    guild = Guild.query.get(guild_id)
    if not guild:
        return jsonify({'error': 'Guild not found'}), 404
    from services.guild_phase1 import can_manage_guild_layer_link

    if not can_manage_guild_layer_link(user, guild, project):
        return jsonify({'error': 'Forbidden'}), 403
    link = GuildLayerLink.query.filter_by(guild_id=guild.id, layer_id=project.id).first()
    if not link:
        return jsonify({'error': 'Link not found'}), 404
    lid = link.id
    db.session.delete(link)
    emit_event(
        'guild_layer_unlinked',
        actor_type='user',
        actor_id=user['id'],
        subject_type='guild_layer_link',
        subject_id=lid,
        layer_id=project.id,
        payload={
            'guild_id': guild.id,
            'guild_name': guild.name,
            'layer_id': project.id,
        },
    )
    db.session.commit()
    return jsonify({'success': True}), 200


@bp.route('/<layer_id>/members/', methods=['GET'])
def list_layer_members(layer_id):
    """List project members."""
    project = Layer.query.get_or_404(layer_id)
    members = LayerMember.query.filter_by(layer_id=layer_id, status='active').all()
    return jsonify({
        'members': [{
            'id': m.id,
            'user_id': m.user_id,
            'username': m.user.username,
            'display_name': m.user.displayName or m.user.username,
            'role': m.role,
            'joined_at': m.joined_at.isoformat() if m.joined_at else None,
            'referred_by': m.referred_by.displayName or m.referred_by.username if m.referred_by else None
        } for m in members]
    }), 200


@bp.route('/<layer_id>/join/', methods=['POST'])
@require_auth
def join_layer(layer_id):
    """Join a project (with optional referral tracking)."""
    current_user_data = get_current_user()
    if not current_user_data:
        return jsonify({'error': 'Authentication required'}), 401

    user = User.query.get(current_user_data['id'])
    project = Layer.query.get_or_404(layer_id)

    jp = getattr(project, 'join_policy', None) or 'open'
    if jp == 'nft_gated':
        from services.nft_gate import load_layer_nft_gate, user_meets_nft_gate

        ok, err = user_meets_nft_gate(user, load_layer_nft_gate(project))
        if not ok:
            return jsonify({'error': err or 'NFT required to join this layer'}), 403
    elif jp == 'by_invitation':
        return jsonify({'error': 'This layer requires an invitation to join'}), 403

    existing = LayerMember.query.filter_by(layer_id=layer_id, user_id=user.id).first()
    was_already_active = (
        existing
        and existing.status == 'active'
        and existing.left_at is None
    )
    if was_already_active:
        return jsonify({'error': 'Already a member of this project'}), 400

    data = request.get_json() or {}
    ref_token = data.get('ref_token')
    from services.referral_attribution import resolve_referrer_from_token, record_referral_attribution

    referred_by_id, token_attr = resolve_referrer_from_token(
        ref_token,
        current_user_id=user.id,
    )

    if existing:
        existing.status = 'active'
        existing.joined_at = datetime.utcnow()
        existing.left_at = None
        if referred_by_id and not existing.referred_by_id:
            existing.referred_by_id = referred_by_id
            existing.referral_code = None
        member = existing
    else:
        member = LayerMember(
            layer_id=layer_id,
            user_id=user.id,
            referred_by_id=referred_by_id,
            referral_code=None,
            role='contributor'
        )
        db.session.add(member)

    if referred_by_id:
        scope_type = (token_attr or {}).get('scope_type') or 'layer'
        scope_id = (token_attr or {}).get('scope_id') or layer_id
        record_referral_attribution(
            referrer_user_id=referred_by_id,
            converted_user_id=user.id,
            scope_type=scope_type,
            scope_id=scope_id,
            entity_type='layer',
            entity_id=layer_id,
            conversion_type='layer_member_join',
            channel=(token_attr or {}).get('channel'),
            campaign=(token_attr or {}).get('campaign'),
            share_event_id=(token_attr or {}).get('share_event_id'),
            referral_token=ref_token,
        )

    emit_event(
        'member_joined',
        actor_type='user',
        actor_id=user.id,
        subject_type='layer_member',
        subject_id=member.id,
        layer_id=layer_id,
        payload={'user_id': user.id, 'role': member.role, 'via': 'join'},
    )
    db.session.commit()

    if not was_already_active:
        try:
            from services.scope_email import enqueue_after_join

            enqueue_after_join(
                scope_type='layer',
                scope_id=layer_id,
                user_id=user.id,
                anchor_kind='layer_member',
                anchor_at=member.joined_at or datetime.utcnow(),
            )
        except Exception:
            current_app.logger.exception('after_join scoped email enqueue failed')

    kind = (getattr(project, 'layer_kind', None) or '').strip()
    if kind != 'auth_community':
        vid = (getattr(user, 'web3authVerifierId', None) or '').strip()
        if vid and getattr(project, 'canopi_meta_community_id', None):
            from services.canopi_community_sync import mirror_membership_to_canopi

            mirror_membership_to_canopi(
                layer_id=layer_id,
                web3auth_verifier_id=vid,
                active=True,
            )

    return jsonify({
        'message': 'Successfully joined project',
        'member': {
            'id': member.id,
            'layer_id': member.layer_id,
            'user_id': member.user_id,
            'role': member.role,
            'joined_at': member.joined_at.isoformat() if member.joined_at else None,
            'referred_by': member.referred_by.displayName or member.referred_by.username if member.referred_by else None
        }
    }), 201


@bp.route('/<layer_id>/leave/', methods=['POST'])
@require_auth
def leave_layer(layer_id):
    """Leave a project."""
    current_user_data = get_current_user()
    if not current_user_data:
        return jsonify({'error': 'Authentication required'}), 401

    user = User.query.get(current_user_data['id'])
    project = Layer.query.get_or_404(layer_id)

    member = LayerMember.query.filter_by(layer_id=layer_id, user_id=user.id, status='active').first()
    if not member:
        return jsonify({'error': 'Not a member of this project'}), 404

    member.status = 'left'
    member.left_at = datetime.utcnow()
    emit_event('member_removed', actor_type='user', actor_id=user.id,
               subject_type='layer_member', subject_id=member.id,
               layer_id=layer_id, payload={'user_id': user.id})
    db.session.commit()

    return jsonify({'message': 'Successfully left project'}), 200


# ============================================================================
# Project admin email (recipients, send)
# ============================================================================

@bp.route('/<layer_id>/email-recipients/', methods=['GET'])
@require_auth
def api_project_email_recipients(layer_id):
    """List recipient groups for project admin email. Project admin only."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    project = Layer.query.get_or_404(layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Layer admin required'}), 403

    from services.resend_mail import get_resend_from
    from services.scope_email import layer_recipient_groups

    from_config = get_resend_from()
    from_addr = (from_config or {}).get('formatted') or 'Gov Hub <no-reply@govhub.live>'
    admin_emails = []
    if project.initiator and project.initiator.email:
        name = project.initiator.displayName or project.initiator.username or 'Initiator'
        admin_emails.append({'value': f"{name} <{project.initiator.email}>", 'label': f"{name} (initiator)"})
    for pa in LayerAdmin.query.filter_by(layer_id=layer_id).all():
        if pa.user and pa.user.email and pa.user_id != project.initiator_id:
            name = pa.user.displayName or pa.user.username or 'Admin'
            admin_emails.append({'value': f"{name} <{pa.user.email}>", 'label': f"{name} (admin)"})

    return jsonify({
        'groups': layer_recipient_groups(layer_id),
        'from_options': [{'value': from_addr, 'label': 'Default (noreply)'}] + admin_emails,
    }), 200


@bp.route('/<layer_id>/send-email/', methods=['POST'])
@require_auth
def api_project_send_email(layer_id):
    """Send or schedule email to selected recipient groups. Layer admin only."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    Layer.query.get_or_404(layer_id)

    data = request.get_json() or {}
    from services.scope_email import create_campaign

    payload, err, code = _parse_scope_email_payload(data)
    if err:
        return jsonify({'error': err}), code

    campaign, err, code = create_campaign(
        scope_type='layer',
        scope_id=layer_id,
        user=current_user,
        **payload,
    )
    if err:
        return jsonify({'error': err}), code
    return jsonify({
        'campaign': campaign.to_dict(),
        'sent': campaign.stats_sent,
        'total': campaign.stats_total,
    }), code


def _parse_scope_email_payload(data: dict):
    from dateutil import parser as date_parser

    groups = data.get('groups') or []
    user_ids = data.get('user_ids') or []
    subject = (data.get('subject') or '').strip()
    body = (data.get('body') or '').strip()
    schedule_mode = (data.get('schedule_mode') or 'immediate').strip().lower()
    scheduled_at = None
    if data.get('scheduled_at'):
        try:
            scheduled_at = date_parser.parse(str(data.get('scheduled_at')))
        except Exception:
            return None, 'Invalid scheduled_at', 400
    delay_hours = data.get('delay_hours')
    if delay_hours is not None and delay_hours != '':
        try:
            delay_hours = float(delay_hours)
        except (TypeError, ValueError):
            return None, 'Invalid delay_hours', 400
    else:
        delay_hours = None
    anchor_kind = (data.get('anchor_kind') or '').strip() or None
    return {
        'groups': groups,
        'user_ids': user_ids,
        'subject': subject,
        'body': body,
        'schedule_mode': schedule_mode,
        'scheduled_at': scheduled_at,
        'delay_hours': delay_hours,
        'anchor_kind': anchor_kind,
    }, None, None


@bp.route('/<layer_id>/invitations/campaign/', methods=['POST'])
@require_auth
def layer_shareable_campaign(layer_id):
    """Return the shareable layer join link (public layers only)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    from services.layer_invitations import get_shareable_layer_campaign

    data = request.get_json() or {}
    body, status = get_shareable_layer_campaign(
        layer_id=layer_id,
        inviter_id=current_user['id'],
        message=data.get('message'),
    )
    return jsonify(body), status


@bp.route('/<layer_id>/invitations/', methods=['GET', 'POST'])
@require_auth
def layer_invitations(layer_id):
    """List or create email invitations (any active layer member)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    from services.layer_invitations import create_layer_invitation, list_layer_invitations

    if request.method == 'GET':
        body, status = list_layer_invitations(layer_id, current_user['id'])
        return jsonify(body), status

    data = request.get_json() or {}
    body, status = create_layer_invitation(
        layer_id=layer_id,
        inviter_id=current_user['id'],
        invitee_email=data.get('email', ''),
        message=data.get('message'),
    )
    return jsonify(body), status


# ============================================================================
# Per-layer two-letter draft prefix CRUD
# ============================================================================
# Endpoint map (all under /api/layers):
#   GET    /<layer_id>/prefixes/                  - list prefixes for a layer
#   POST   /<layer_id>/prefixes/                  - add a new prefix (layer admin)
#   PATCH  /<layer_id>/prefixes/<prefix_id>/      - rename a prefix (layer admin)
#   DELETE /<layer_id>/prefixes/<prefix_id>/      - delete a prefix (layer admin)
#   POST   /<layer_id>/prefixes/<prefix_id>/default/ - mark default (layer admin)
#   GET    /my-prefixes/                          - all prefixes for layers the user can access
#   POST   /active-prefix/                        - set the current draft prefix (auth required)
#
# The auth + permission checks follow the same pattern as the rest of
# routes/layers.py: ``@require_auth`` plus an explicit ``is_layer_admin`` for
# write endpoints.

ACTIVE_PREFIX_SESSION_KEY = 'active_layer_prefix_id'


def _ensure_layer_for_prefixes(layer_id):
    layer = Layer.query.get(layer_id)
    if not layer:
        layer = Layer.query.filter_by(slug=layer_id).first()
    return layer


@bp.route('/<layer_id>/prefixes/', methods=['GET'])
def list_layer_prefixes(layer_id):
    """List all two-letter draft prefixes for a layer.

    Anonymous read access — the list is the same public knowledge as the
    layer's draft codes are deterministic from the layer existence.
    """
    project = _ensure_layer_for_prefixes(layer_id)
    if not project:
        return jsonify({'error': 'Layer not found', 'code': 'not_found'}), 404

    rows = _svc_list_prefixes(project.id)
    return jsonify({
        'prefixes': [r.to_dict() for r in rows],
        'count': len(rows),
    }), 200


@bp.route('/<layer_id>/prefixes/', methods=['POST'])
@require_auth
def add_layer_prefix(layer_id):
    """Add a new two-letter prefix to a layer. Layer admin only."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    project = _ensure_layer_for_prefixes(layer_id)
    if not project:
        return jsonify({'error': 'Layer not found', 'code': 'not_found'}), 404

    if not is_layer_admin(project, current_user):
        return jsonify({
            'error': 'Only layer admins can add prefixes',
            'code': 'forbidden',
        }), 403

    data = request.get_json() or {}
    body, status = _svc_add_prefix(
        project.id, data.get('prefix', ''), current_user.get('id'),
    )
    return jsonify(body), status


@bp.route('/<layer_id>/prefixes/<prefix_id>/', methods=['PATCH'])
@require_auth
def update_layer_prefix(layer_id, prefix_id):
    """Rename a prefix. Layer admin only."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    project = _ensure_layer_for_prefixes(layer_id)
    if not project:
        return jsonify({'error': 'Layer not found', 'code': 'not_found'}), 404

    if not is_layer_admin(project, current_user):
        return jsonify({
            'error': 'Only layer admins can rename prefixes',
            'code': 'forbidden',
        }), 403

    data = request.get_json() or {}
    body, status = _svc_update_prefix(
        project.id, prefix_id, data.get('prefix', ''),
    )
    return jsonify(body), status


@bp.route('/<layer_id>/prefixes/<prefix_id>/', methods=['DELETE'])
@require_auth
def delete_layer_prefix(layer_id, prefix_id):
    """Delete a prefix. Layer admin only.

    Refuses the layer default and the last remaining prefix; those 400s
    come back from the service layer with stable codes so the UI can
    surface precise errors via GhDialog.
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    project = _ensure_layer_for_prefixes(layer_id)
    if not project:
        return jsonify({'error': 'Layer not found', 'code': 'not_found'}), 404

    if not is_layer_admin(project, current_user):
        return jsonify({
            'error': 'Only layer admins can delete prefixes',
            'code': 'forbidden',
        }), 403

    body, status = _svc_delete_prefix(project.id, prefix_id)
    return jsonify(body), status


@bp.route('/<layer_id>/prefixes/<prefix_id>/default/', methods=['POST'])
@require_auth
def set_default_layer_prefix(layer_id, prefix_id):
    """Mark a prefix as the layer default (clears any other default)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    project = _ensure_layer_for_prefixes(layer_id)
    if not project:
        return jsonify({'error': 'Layer not found', 'code': 'not_found'}), 404

    if not is_layer_admin(project, current_user):
        return jsonify({
            'error': 'Only layer admins can set the default prefix',
            'code': 'forbidden',
        }), 403

    body, status = _svc_set_default_prefix(project.id, prefix_id)
    return jsonify(body), status


@bp.route('/my-prefixes/', methods=['GET'])
def my_layer_prefixes():
    """All prefixes for layers the current user can access.

    Anonymous users get an empty list (the JS uses this to show a
    "sign in" hint). For full functionality the user must be a layer
    admin, an active layer member, or the layer owner.
    """
    from flask import has_request_context, session

    user_id = None
    if has_request_context():
        cur = get_current_user()
        if cur and isinstance(cur, dict):
            user_id = cur.get('id')

    prefixes = _svc_prefixes_for_user(user_id)
    return jsonify({'prefixes': prefixes, 'count': len(prefixes)}), 200


@bp.route('/active-prefix/', methods=['POST'])
@require_auth
def set_active_prefix():
    """Persist the user's chosen draft prefix in their session.

    Body: ``{"prefix_id": "<UUID>"}``. Returns the chosen prefix row so
    the chip + any page-level consumers can update in place.
    """
    from flask import session

    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json() or {}
    prefix_id = (data.get('prefix_id') or '').strip()
    if not prefix_id:
        return jsonify({'error': 'prefix_id is required', 'code': 'invalid_format'}), 400

    from models import LayerPrefix

    prefix = LayerPrefix.query.get(prefix_id)
    if not prefix:
        return jsonify({'error': 'Prefix not found', 'code': 'not_found'}), 404

    user_id = current_user.get('id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    # Authorize: user must be a layer admin, an active member, or the
    # layer owner for the prefix's owning layer.
    from models import LayerAdmin, LayerMember

    project = Layer.query.get(prefix.layer_id)
    if not project:
        return jsonify({'error': 'Layer not found', 'code': 'not_found'}), 404

    authorized = (
        project.initiator_id == user_id
        or LayerAdmin.query.filter_by(layer_id=project.id, user_id=user_id).first()
        or LayerMember.query.filter_by(
            layer_id=project.id, user_id=user_id, status='active',
        ).first()
        or current_user.get('role') == 'admin'
    )
    if not authorized:
        return jsonify({
            'error': 'You do not have access to this prefix',
            'code': 'forbidden',
        }), 403

    session[ACTIVE_PREFIX_SESSION_KEY] = prefix_id
    return jsonify({'prefix': prefix.to_dict()}), 200


@bp.route('/active-prefix/', methods=['GET'])
def get_active_prefix():
    """Return the user's currently-active draft prefix, if any.

    Resolution order: session → first available layer default for a
    layer the user can access. Anonymous users get an empty response.
    """
    from flask import has_request_context, session

    cur = None
    user_id = None
    if has_request_context():
        cur = get_current_user()
        if cur and isinstance(cur, dict):
            user_id = cur.get('id')

    active_id = session.get(ACTIVE_PREFIX_SESSION_KEY) if has_request_context() else None
    if active_id:
        from models import LayerPrefix

        prefix = LayerPrefix.query.get(active_id)
        if prefix:
            return jsonify({'prefix': prefix.to_dict()}), 200

    if not user_id:
        return jsonify({'prefix': None}), 200

    available = _svc_prefixes_for_user(user_id)
    for p in available:
        if p.get('is_default'):
            return jsonify({'prefix': p}), 200
    if available:
        return jsonify({'prefix': available[0]}), 200
    return jsonify({'prefix': None}), 200


@bp.route('/<layer_id>/display-status/', methods=['POST'])
@require_auth
def set_layer_display_status(layer_id):
    """Flip a layer's ``display_status`` (``pending`` ↔ ``active``).

    Layer-admin only (this is the "Public visibility" toggle on the layer's
    Edit page). Independent from the GovHub super-admin
    ``approval_status`` workflow: a layer that has been approved by
    GovHub can still be hidden until the layer admin flips it to active.

    Body: ``{"display_status": "active"|"pending"}``.
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    project = _ensure_layer_for_prefixes(layer_id)
    if not project:
        return jsonify({'error': 'Layer not found', 'code': 'not_found'}), 404

    if not is_layer_admin(project, current_user):
        return jsonify({
            'error': 'Only layer admins can change display status',
            'code': 'forbidden',
        }), 403

    data = request.get_json() or {}
    raw_value = data.get('display_status')
    if raw_value is None:
        return jsonify({
            'error': 'display_status is required',
            'code': 'invalid_value',
        }), 400
    # Reject unknown values explicitly (normalize_display_status falls back to
    # 'pending', but for an explicit API toggle we want 400 so the caller
    # knows the value was invalid rather than silently flipped).
    raw_norm = str(raw_value).strip().lower()
    if raw_norm not in ('pending', 'active'):
        return jsonify({
            'error': 'display_status must be either "pending" or "active"',
            'code': 'invalid_value',
        }), 400
    new_status = raw_norm

    old_status = getattr(project, 'display_status', 'pending') or 'pending'
    project.display_status = new_status
    db.session.commit()

    return jsonify({
        'success': True,
        'layer_id': project.id,
        'display_status': new_status,
        'previous_display_status': old_status,
    }), 200
