"""User API: search, referral code, profile, uploads (entity + profile images)."""
import json

from flask import Blueprint, jsonify, request, send_from_directory, current_app

from sqlalchemy import or_

from extensions import db
from models import User, LayerMember
from services.identity import get_current_user, require_auth, get_or_create_referral_code
from services.avatar import get_avatar_url
from services.images import upload_image_600x600, upload_image

bp = Blueprint('users', __name__, url_prefix='')


def _entity_image_folder():
    return current_app.config.get('ENTITY_IMAGE_UPLOAD_FOLDER', '/home/ubuntu/data-tracker/uploads/entity_images')


def _profile_image_folder():
    return current_app.config.get('PROFILE_IMAGE_UPLOAD_FOLDER', '/home/ubuntu/data-tracker/uploads/profile_images')


# ============================================================================
# Entity image upload (projects, workgroups, guilds, waitlists)
# ============================================================================

@bp.route('/api/upload/entity-image', methods=['POST'])
@require_auth
def api_upload_entity_image():
    """Upload an image for project/workgroup/guild/waitlist. Max 600×600, 5MB. Returns { image_url }."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    entity_type = (request.form.get('entity_type') or 'entity').strip()[:20].replace('/', '_') or 'entity'
    prefix = entity_type.lower()
    image_url, err = upload_image_600x600(
        file, _entity_image_folder(), '/uploads/entity_images', filename_prefix=prefix
    )
    if err:
        return jsonify({'error': err}), 400
    return jsonify({'success': True, 'image_url': image_url}), 201


@bp.route('/uploads/entity_images/<filename>')
def serve_entity_image(filename):
    """Serve uploaded entity images (projects, workgroups, guilds, waitlists)"""
    return send_from_directory(_entity_image_folder(), filename)


# ============================================================================
# User search
# ============================================================================

@bp.route('/api/users/search/', methods=['GET'])
@require_auth
def api_search_users():
    """Search users by username or display name (authenticated; for admin/coordinator UI)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({'users': [], 'count': 0})

    users = User.query.filter(
        or_(
            User.username.ilike(f'%{q}%'),
            User.displayName.ilike(f'%{q}%'),
            User.name.ilike(f'%{q}%')
        )
    ).limit(20).all()

    return jsonify({
        'users': [{'id': u.id, 'username': u.username, 'display_name': u.displayName or u.username} for u in users],
        'count': len(users)
    })


# ============================================================================
# Referral code
# ============================================================================

@bp.route('/api/user/referral-code/', methods=['GET'])
@require_auth
def api_get_referral_code():
    """Get current user's referral code"""
    current_user_data = get_current_user()
    if not current_user_data:
        return jsonify({'error': 'Authentication required'}), 401

    user = User.query.get(current_user_data['id'])
    referral_code = get_or_create_referral_code(user)

    # Count referrals
    referral_count = LayerMember.query.filter_by(referred_by_id=user.id).count()

    return jsonify({
        'referral_code': referral_code,
        'referral_count': referral_count,
        'referral_url': f"{request.host_url}?ref={referral_code}"
    }), 200


# ============================================================================
# User profile API
# ============================================================================

@bp.route('/api/user/<username>/', methods=['GET'])
def api_get_user_profile(username):
    """Get user profile data"""
    user = User.query.filter_by(username=username).first()
    if not user:
        user = User.query.filter_by(handle=username).first()

    if not user:
        return jsonify({'error': 'User not found'}), 404

    social_links = []
    if user.social_links:
        try:
            social_links = json.loads(user.social_links)
        except Exception:
            social_links = []

    return jsonify({
        'id': user.id,
        'username': user.username,
        'displayName': user.displayName,
        'handle': user.handle,
        'profileImage': get_avatar_url(user, 200),
        'banner_image': user.banner_image,
        'headline': user.headline,
        'bio': user.bio,
        'social_links': social_links,
        'role': user.role,
        'created_at': user.created_at.isoformat() if user.created_at else None
    })


@bp.route('/api/user/profile/', methods=['PUT'])
@require_auth
def api_update_user_profile():
    """Update current user's profile"""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    user = User.query.get(current_user['id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json()

    # Update allowed fields
    if 'headline' in data:
        user.headline = data['headline'][:200]  # Max 200 chars

    if 'bio' in data:
        user.bio = data['bio']

    if 'social_links' in data:
        user.social_links = json.dumps(data['social_links'])

    if 'email_notifications_opt_in' in data:
        user.email_notifications_opt_in = bool(data['email_notifications_opt_in'])

    if 'email_digest_mode' in data:
        mode = (data['email_digest_mode'] or 'immediate').strip().lower()
        if mode not in ('immediate', 'daily', 'weekly', 'off'):
            return jsonify({'error': 'email_digest_mode must be immediate, daily, weekly, or off'}), 400
        user.email_digest_mode = mode

    db.session.commit()

    return jsonify({'success': True, 'message': 'Profile updated successfully'})


# ============================================================================
# Profile image upload
# ============================================================================

@bp.route('/uploads/profile_images/<filename>')
def serve_profile_image(filename):
    """Serve uploaded profile/banner images"""
    return send_from_directory(_profile_image_folder(), filename)


@bp.route('/api/user/upload-image', methods=['POST'])
@bp.route('/api/user/upload-image/', methods=['POST'])
@require_auth
def api_upload_profile_image():
    """Upload profile or banner image. Max 600×600px, 5MB."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    user = User.query.get(current_user['id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    image_type = request.form.get('type', 'profile')  # 'profile' or 'banner'

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    prefix = f"{image_type}_{user.id}"
    if image_type == 'banner':
        image_url, err = upload_image(
            file, _profile_image_folder(), '/uploads/profile_images',
            filename_prefix=prefix, max_dimension=None
        )
    else:
        image_url, err = upload_image_600x600(
            file, _profile_image_folder(), '/uploads/profile_images', filename_prefix=prefix
        )
    if err:
        return jsonify({'error': err}), 400

    if image_type == 'profile':
        user.profileImage = image_url
    elif image_type == 'banner':
        user.banner_image = image_url

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Image uploaded successfully',
        'url': image_url
    })
