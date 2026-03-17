"""Deployment and health check routes. Uses current_app.config for env vars."""
import os
import shutil
import subprocess
from datetime import datetime

from flask import Blueprint, jsonify, current_app, g, request
from extensions import db

bp = Blueprint('deploy', __name__, url_prefix='')


@bp.route('/_deploy/reload', methods=['POST'])
def reload_app():
    """Reload the application - development only."""
    if not current_app.config.get('IS_DEVELOPMENT', False):
        return jsonify({'error': 'Not available in production'}), 403

    cache_dirs = []
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for root, dirs, files in os.walk(root_dir):
        if '__pycache__' in dirs:
            cache_dirs.append(os.path.join(root, '__pycache__'))
        for f in files:
            if f.endswith('.pyc'):
                try:
                    os.remove(os.path.join(root, f))
                except Exception:
                    pass

    for cache_dir in cache_dirs:
        try:
            shutil.rmtree(cache_dir)
        except Exception:
            pass

    return jsonify({
        'status': 'success',
        'message': 'Cache cleared. Service restart required.',
        'restart_command': 'systemctl --user restart datatracker-dev.service'
    })


@bp.route('/_deploy/status', methods=['GET'])
def deployment_status():
    """Check deployment status - comprehensive status endpoint."""
    is_dev = current_app.config.get('IS_DEVELOPMENT', False)
    db_path = current_app.config.get('DB_PATH', '')
    env = current_app.config.get('ENV', 'production')
    port = current_app.config.get('PORT', 8000)
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    git_branch = 'unknown'
    git_commit = 'unknown'
    git_commit_short = 'unknown'
    try:
        result = subprocess.run(['git', 'branch', '--show-current'],
                               capture_output=True, text=True, timeout=2, cwd=root_dir)
        if result.returncode == 0:
            git_branch = result.stdout.strip() or 'unknown'
    except Exception:
        pass

    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'],
                               capture_output=True, text=True, timeout=2, cwd=root_dir)
        if result.returncode == 0:
            git_commit = result.stdout.strip() or 'unknown'
            git_commit_short = git_commit[:8] if len(git_commit) > 8 else git_commit
    except Exception:
        pass

    service_name = f'datatracker{"-dev" if is_dev else ""}.service'
    service_active = None
    try:
        result = subprocess.run(['systemctl', '--user', 'is-active', service_name],
                               capture_output=True, text=True, timeout=2)
        service_active = result.returncode == 0
    except Exception:
        pass

    db_exists = os.path.exists(db_path)
    db_size = 0
    if db_exists:
        try:
            db_size = os.path.getsize(db_path)
        except Exception:
            pass

    status = {
        'environment': env,
        'port': port,
        'database': {
            'path': db_path,
            'exists': db_exists,
            'size_bytes': db_size,
            'size_mb': round(db_size / 1024 / 1024, 2) if db_size > 0 else 0
        },
        'git': {
            'branch': git_branch,
            'commit': git_commit,
            'commit_short': git_commit_short
        },
        'service': {
            'name': service_name,
            'active': service_active
        },
        'deployed_at': datetime.now().isoformat(),
        'version': '2026-01-17-v2'
    }

    return jsonify(status)


@bp.route('/_deploy/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    is_dev = current_app.config.get('IS_DEVELOPMENT', False)
    service_name = f'datatracker{"-dev" if is_dev else ""}.service'

    db_healthy = False
    try:
        db.session.execute(db.text('SELECT 1'))
        db_healthy = True
    except Exception:
        pass

    service_healthy = None
    try:
        result = subprocess.run(['systemctl', '--user', 'is-active', service_name],
                               capture_output=True, text=True, timeout=2)
        service_healthy = result.returncode == 0
    except Exception:
        pass

    overall_healthy = db_healthy and (service_healthy is True)

    return jsonify({
        'status': 'healthy' if overall_healthy else 'unhealthy',
        'database': 'connected' if db_healthy else 'disconnected',
        'service': 'active' if service_healthy else 'inactive',
        'timestamp': datetime.now().isoformat()
    }), 200 if overall_healthy else 503


@bp.route('/_deploy/host-info', methods=['GET'])
def host_info():
    """Debug: Host header and layer resolution (for subdomain redirect troubleshooting)."""
    host = request.host
    xfh = request.headers.get('X-Forwarded-Host', '')
    layer = getattr(g, 'layer', None)
    return jsonify({
        'host': host,
        'host_lower': host.split(':')[0].lower() if host else '',
        'X-Forwarded-Host': xfh,
        'path': request.path,
        'g.layer': layer.to_dict() if layer else None,
        'g.layer_slug': getattr(g, 'layer_slug', None),
        'would_redirect': layer is not None and request.path == '/',
    })


@bp.route('/_deploy/test', methods=['GET'])
def deployment_test():
    """Show a visible test page."""
    env = current_app.config.get('ENV', 'production')
    port = current_app.config.get('PORT', 8000)
    db_path = current_app.config.get('DB_PATH', '')
    return f"""
    <html>
    <head><title>Deployment Test</title></head>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h1 style="color: red;">🚨 DEPLOYMENT TEST PAGE 🚨</h1>
        <div style="background-color: #ffcccc; border: 3px solid red; padding: 20px; margin: 20px 0; border-radius: 10px;">
            <h2 style="color: red;">If you can see this page, the deployment worked!</h2>
            <p><strong>Environment:</strong> {env}</p>
            <p><strong>Port:</strong> {port}</p>
            <p><strong>Database:</strong> {db_path}</p>
            <p><strong>Time:</strong> {datetime.now()}</p>
        </div>
        <p><a href="/">← Back to main site</a></p>
    </body>
    </html>
    """
