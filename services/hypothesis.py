"""Hypothesis annotation services: config, account creation, annotations, embed config."""
import os
import time

from flask import request, current_app

from extensions import db
from models import HypothesisAccount


# Hypothesis Annotation Configuration
HYPOTHESIS_ENABLED = True  # Set to False to disable annotations globally
HYPOTHESIS_CONFIG = {
    'EMBED_URL': 'https://hypothes.is/embed.js',
    'API_URL': 'https://hypothes.is/api',
    'API_TOKEN': os.getenv('HYPOTHESIS_API_TOKEN'),  # Server-only: read/count; never sent to client
    'AUTHORITY': 'hypothes.is',  # Use hypothes.is authority for now
    'BRANDING': {
        'appBackgroundColor': '#16181c',  # Dark theme background
        'ctaBackgroundColor': '#1d9bf0',  # Meta-Layer accent color
        'ctaTextColor': '#ffffff',
        'selectionFontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    },
    'ENABLE_EXPERIMENTAL_NEW_NOTE_BUTTON': True,
    'SHOW_HIGHLIGHTS': 'whenSidebarOpen',
}


def create_hypothesis_account(user):
    """Create a Hypothesis account for a Meta-Layer user via API"""
    import requests

    # Check if user already has a Hypothesis account
    existing = HypothesisAccount.query.filter_by(user_id=user['id']).first()
    if existing:
        return existing

    if not HYPOTHESIS_CONFIG.get('API_TOKEN'):
        current_app.logger.error("No Hypothesis API token configured")
        return None

    # Generate unique username
    base_username = user.get('displayName', user.get('username', f'user{user["id"]}'))
    # Clean username (Hypothesis requirements: alphanumeric + hyphens + underscores)
    clean_username = ''.join(c for c in base_username if c.isalnum() or c in '-_').lower()
    if not clean_username:
        clean_username = f'mluser{user["id"]}'

    # Ensure uniqueness by adding timestamp
    username = f"{clean_username}_{int(time.time())}"

    try:
        headers = {
            'Authorization': f'Bearer {HYPOTHESIS_CONFIG["API_TOKEN"]}',
            'Content-Type': 'application/json'
        }

        hypothesis_userid = f"acct:{username}@hypothes.is"

        # Store the account link (Hypothesis API doesn't have direct user creation)
        hypothesis_account = HypothesisAccount(
            user_id=user['id'],
            hypothesis_username=username,
            hypothesis_userid=hypothesis_userid
        )
        db.session.add(hypothesis_account)
        db.session.commit()

        current_app.logger.info(f"Created Hypothesis account mapping for user {user['id']}: {username}")
        return hypothesis_account

    except Exception as e:
        current_app.logger.error(f"Failed to create Hypothesis account for user {user['id']}: {e}")
        return None


def get_document_annotations(document_name, document_type='draft'):
    """Fetch existing annotations for a document using Hypothesis API"""
    import requests

    if not HYPOTHESIS_CONFIG.get('API_TOKEN'):
        return []

    try:
        headers = {
            'Authorization': f'Bearer {HYPOTHESIS_CONFIG["API_TOKEN"]}',
            'Content-Type': 'application/json'
        }

        tag = f"{document_type}:{document_name}"
        url = f"{HYPOTHESIS_CONFIG['API_URL']}/search"
        params = {
            'tag': tag,
            'limit': 200  # Maximum per request
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('rows', [])
        else:
            current_app.logger.warning(f"Failed to fetch annotations: {response.status_code}")
            return []

    except Exception as e:
        current_app.logger.error(f"Error fetching annotations: {e}")
        return []


def create_annotation_via_api(document_name, document_type, text, quote, user):
    """Create annotation via Hypothesis API.
    WARNING: Uses the server's API token, so the annotation would be attributed to the
    token owner (you), NOT the end user. Do NOT use for user-created content.
    Only use for system/bot annotations if ever needed. User annotations are created
    by the Hypothesis client in the browser under each user's own account.
    """
    import requests

    if not HYPOTHESIS_CONFIG.get('API_TOKEN'):
        return None

    try:
        headers = {
            'Authorization': f'Bearer {HYPOTHESIS_CONFIG["API_TOKEN"]}',
            'Content-Type': 'application/json'
        }

        annotation_data = {
            'uri': f'https://dev.rfc.themetalayer.org/doc/{document_type}/{document_name}/',
            'text': text,
            'tags': [f'{document_type}:{document_name}', f'meta-layer:{document_type}'],
            'target': [{
                'source': f'https://dev.rfc.themetalayer.org/doc/{document_type}/{document_name}/',
                'selector': [{
                    'type': 'TextQuoteSelector',
                    'exact': quote
                }]
            }],
            'permissions': {
                'read': ['group:__world__'],
                'update': [f'acct:{user.get("username", "anonymous")}@hypothes.is'],
                'delete': [f'acct:{user.get("username", "anonymous")}@hypothes.is'],
                'admin': [f'acct:{user.get("username", "anonymous")}@hypothes.is']
            }
        }

        response = requests.post(
            f"{HYPOTHESIS_CONFIG['API_URL']}/annotations",
            headers=headers,
            json=annotation_data,
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            current_app.logger.warning(f"Failed to create annotation: {response.status_code}")
            return None

    except Exception as e:
        current_app.logger.error(f"Error creating annotation: {e}")
        return None


def generate_hypothesis_config(document_name=None, document_type='draft'):
    """Generate Hypothesis configuration HTML for document pages"""
    if not HYPOTHESIS_ENABLED:
        return ""

    # Check if user has annotations enabled (via cookie)
    annotations_enabled = request.cookies.get('annotations', 'off') == 'on'
    if not annotations_enabled:
        return ""

    # Get current user
    from services.identity import get_current_user
    current_user = get_current_user()

    # Generate document-specific tags
    if document_type == 'draft':
        tags = f'["draft:{document_name}", "meta-layer:draft"]'
    else:
        tags = f'["{document_type}:{document_name}", "meta-layer:{document_type}"]'

    auth_config = ""

    return f"""
    <script>
    window.hypothesisConfig = function () {{
      return {{
        branding: {{
          appBackgroundColor: '{HYPOTHESIS_CONFIG['BRANDING']['appBackgroundColor']}',
          ctaBackgroundColor: '{HYPOTHESIS_CONFIG['BRANDING']['ctaBackgroundColor']}',
          ctaTextColor: '{HYPOTHESIS_CONFIG['BRANDING']['ctaTextColor']}',
          selectionFontFamily: '{HYPOTHESIS_CONFIG['BRANDING']['selectionFontFamily']}'
        }},
        enableExperimentalNewNoteButton: {str(HYPOTHESIS_CONFIG['ENABLE_EXPERIMENTAL_NEW_NOTE_BUTTON']).lower()},
        showHighlights: '{HYPOTHESIS_CONFIG['SHOW_HIGHLIGHTS']}',
        openSidebar: false,{auth_config}
        // Focus on document-specific annotations
        focus: {{
          user: {{
            filter: {{
              any: {{
                tag: {tags}
              }}
            }}
          }}
        }}
      }};
    }};
    </script>
    <script async src="{HYPOTHESIS_CONFIG['EMBED_URL']}"></script>
    """
