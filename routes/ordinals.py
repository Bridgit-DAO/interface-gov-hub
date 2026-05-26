"""Ordinals API: preview, convert-markdown, inscribe wizard, inscription (Unisat). Page routes: /immortalize/, /inscribe/."""
import os
import re
import random
import string
from datetime import datetime

import requests
from flask import Blueprint, jsonify, request, redirect, session, current_app

from extensions import db
from models import Submission, SiteConfig, InscriptionOrder
from services.ordinals import process_ordinal_markdown
from services.identity import require_auth
from services.directory_ui import gh_page_header, gh_breadcrumb, gh_living_module

bp = Blueprint('ordinals', __name__, url_prefix='/api')
bp_pages = Blueprint('ordinals_pages', __name__, url_prefix='')


def _get_site_config(key, default):
    """Get SiteConfig value or default."""
    row = SiteConfig.query.filter_by(key=key).first()
    return row.value if row else default


@bp.route('/ordinal/preview', methods=['POST'])
def preview_ordinal():
    """Preview ordinal content and fetch metadata."""
    try:
        data = request.get_json()
        inscription_id = (data.get('inscriptionId') or '').strip()
        if not inscription_id:
            return jsonify({'success': False, 'error': 'Inscription ID is required'}), 400
        if len(inscription_id) < 10 or not all(c.isalnum() or c in 'i-_' for c in inscription_id):
            return jsonify({'success': False, 'error': 'Invalid inscription ID format'}), 400

        content_url = f"https://ordinals.com/content/{inscription_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Connection': 'keep-alive'
        }
        try:
            head_response = requests.head(content_url, headers=headers, timeout=10, allow_redirects=True)
            if head_response.status_code == 404:
                return jsonify({'success': False, 'error': 'Inscription not found'}), 404
            if head_response.status_code == 403:
                return jsonify({
                    'success': False,
                    'error': 'Access denied by ordinals.com. The inscription exists but cannot be accessed from the server. You can view it directly at: ' + content_url
                }), 403
            if head_response.status_code != 200:
                return jsonify({'success': False, 'error': f'Failed to fetch inscription (status: {head_response.status_code})'}), 400

            content_length = int(head_response.headers.get('Content-Length', 0))
            max_size = 50 * 1024
            if content_length == 0:
                try:
                    get_response = requests.get(content_url, headers=headers, timeout=10, stream=True)
                    content_chunk = get_response.raw.read(max_size + 1)
                    content_length = len(content_chunk)
                except Exception:
                    content_length = 1

            if content_length > max_size:
                return jsonify({'success': False, 'error': f'Content too large: {content_length/1024:.1f}KB (max 50KB)'}), 400

            content_type = head_response.headers.get('Content-Type', 'unknown').lower()
            supported_types = [
                'image/png', 'image/jpeg', 'image/jpg', 'image/gif',
                'image/svg+xml', 'image/webp',
                'text/plain', 'text/markdown', 'text/html', 'text/javascript',
                'application/json', 'application/javascript'
            ]
            if not any(st in content_type for st in supported_types):
                return jsonify({'success': False, 'error': f'Unsupported content type: {content_type}'}), 400

            inscription_number = block_height = timestamp = None
            try:
                page_url = f"https://ordinals.com/inscription/{inscription_id}"
                page_response = requests.get(page_url, headers=headers, timeout=10)
                if page_response.status_code == 200:
                    html = page_response.text
                    number_match = re.search(r'<title>Inscription (\d+)</title>', html)
                    if number_match:
                        inscription_number = int(number_match.group(1))
                    height_match = re.search(r'<dt>height</dt>\s*<dd><a[^>]*>(\d+)</a></dd>', html)
                    if height_match:
                        block_height = int(height_match.group(1))
                    time_match = re.search(r'<dt>timestamp</dt>\s*<dd><time[^>]*>([^<]+)</time></dd>', html)
                    if time_match:
                        timestamp = time_match.group(1).strip()
            except Exception as e:
                current_app.logger.warning(f"Metadata scrape failed: {e}")

            return jsonify({
                'success': True,
                'contentUrl': content_url,
                'contentType': content_type,
                'contentSize': content_length,
                'inscriptionId': inscription_id,
                'inscriptionNumber': inscription_number,
                'blockHeight': block_height,
                'timestamp': timestamp
            })
        except requests.Timeout:
            return jsonify({'success': False, 'error': 'Request timed out. Please try again.'}), 408
        except requests.ConnectionError:
            return jsonify({'success': False, 'error': 'Ordinals service unavailable. Please try again later.'}), 503
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    except Exception as e:
        current_app.logger.exception('Ordinal preview error')
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@bp.route('/ordinal/convert-markdown', methods=['POST'])
def convert_markdown():
    """Convert markdown to HTML with sanitization."""
    try:
        data = request.get_json()
        markdown_text = data.get('markdown', '')
        if not markdown_text:
            return jsonify({'success': False, 'error': 'No markdown provided'}), 400
        html_content = process_ordinal_markdown(markdown_text)
        return jsonify({'success': True, 'html': html_content})
    except Exception as e:
        current_app.logger.exception('Markdown conversion error')
        return jsonify({'success': False, 'error': 'Conversion failed'}), 500


@bp.route('/inscribe/calculate/', methods=['POST'])
def inscribe_calculate():
    """Calculate price given page_count, image_count, optional tier."""
    try:
        data = request.get_json() or {}
        page_count = int(data.get('page_count', 1))
        image_count = int(data.get('image_count', 0))
        tier = int(data.get('tier', 1))
        price_per_page = float(_get_site_config('inscribe_price_per_page', '10.00'))
        price_per_image = float(_get_site_config('inscribe_price_per_image', '5.00'))
        tier2 = int(_get_site_config('inscribe_tier2_discount', '30'))
        tier3 = int(_get_site_config('inscribe_tier3_discount', '50'))
        from tier_pricing import get_inscribe_price
        result = get_inscribe_price(page_count, image_count, tier, price_per_page, price_per_image, tier2, tier3)
        return jsonify({'success': True, **result})
    except Exception as e:
        current_app.logger.exception('inscribe calculate error')
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/inscribe/send-otp/', methods=['POST'])
def inscribe_send_otp():
    """Send OTP via Twilio Verify."""
    try:
        data = request.get_json() or {}
        phone = (data.get('phone') or '').strip()
        if not phone:
            return jsonify({'success': False, 'error': 'Phone number required'}), 400
        sid = os.environ.get('TWILIO_ACCOUNT_SID', '').strip()
        token = os.environ.get('TWILIO_AUTH_TOKEN', '').strip()
        verify_sid = os.environ.get('TWILIO_VERIFY_SID', '').strip()
        if not all([sid, token, verify_sid]):
            return jsonify({'success': False, 'error': 'SMS verification not configured'}), 503
        from twilio.rest import Client
        client = Client(sid, token)
        client.verify.v2.services(verify_sid).verifications.create(to=phone, channel='sms')
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.exception('send-otp error')
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/inscribe/verify-otp/', methods=['POST'])
def inscribe_verify_otp():
    """Verify OTP; return tier and final price."""
    try:
        data = request.get_json() or {}
        phone = (data.get('phone') or '').strip()
        code = (data.get('code') or '').strip()
        page_count = int(data.get('page_count', 1))
        image_count = int(data.get('image_count', 0))
        if not phone or not code:
            return jsonify({'success': False, 'error': 'Phone and code required'}), 400
        sid = os.environ.get('TWILIO_ACCOUNT_SID', '').strip()
        token = os.environ.get('TWILIO_AUTH_TOKEN', '').strip()
        verify_sid = os.environ.get('TWILIO_VERIFY_SID', '').strip()
        if not all([sid, token, verify_sid]):
            return jsonify({'success': False, 'error': 'SMS verification not configured'}), 503
        from twilio.rest import Client
        from tier_pricing import get_tier_for_phone, get_inscribe_price
        client = Client(sid, token)
        check = client.verify.v2.services(verify_sid).verification_checks.create(to=phone, code=code)
        if check.status != 'approved':
            return jsonify({'success': False, 'error': 'Invalid or expired code'}), 400
        tier = get_tier_for_phone(phone)
        price_per_page = float(_get_site_config('inscribe_price_per_page', '10.00'))
        price_per_image = float(_get_site_config('inscribe_price_per_image', '5.00'))
        tier2 = int(_get_site_config('inscribe_tier2_discount', '30'))
        tier3 = int(_get_site_config('inscribe_tier3_discount', '50'))
        result = get_inscribe_price(page_count, image_count, tier, price_per_page, price_per_image, tier2, tier3)
        return jsonify({'success': True, 'tier': tier, 'phone': phone, **result})
    except Exception as e:
        current_app.logger.exception('verify-otp error')
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/inscribe/create-payment/', methods=['POST'])
def inscribe_create_payment():
    """Create InscriptionOrder + Stripe PaymentIntent; return client_secret."""
    try:
        import stripe
        data = request.get_json() or {}
        content_text = data.get('content_text')
        content_filename = data.get('content_filename', 'content.txt')
        page_count = int(data.get('page_count', 1))
        image_count = int(data.get('image_count', 0))
        phone = (data.get('phone') or '').strip()
        tier = int(data.get('tier', 1))
        final_price_usd = float(data.get('final_price_usd', 0))
        acknowledged_timing = data.get('acknowledged_timing') is True
        notify_when_ready = data.get('notify_when_ready') is True
        title = data.get('title', '')
        authors = data.get('authors') or []
        abstract = data.get('abstract', '')
        workgroup = data.get('workgroup', '')
        layer_id = data.get('layer_id') or data.get('project_id')

        if not acknowledged_timing:
            return jsonify({'success': False, 'error': 'You must acknowledge that times to receive may vary'}), 400
        if not content_text and not data.get('content_file_b64'):
            return jsonify({'success': False, 'error': 'Content required'}), 400
        if data.get('content_file_b64') and not content_text:
            content_text = f"[File: {content_filename}]"
        if final_price_usd <= 0:
            return jsonify({'success': False, 'error': 'Invalid price'}), 400

        sk = os.environ.get('STRIPE_SECRET_KEY', '').strip()
        if not sk:
            return jsonify({'success': False, 'error': 'Stripe not configured'}), 503

        stripe.api_key = sk
        amount_cents = int(round(final_price_usd * 100))

        order = InscriptionOrder(
            content_text=content_text or '',
            content_filename=content_filename,
            page_count=page_count,
            image_count=image_count,
            phone_number=phone,
            tier=tier,
            base_price_usd=float(data.get('base_price_usd', final_price_usd)),
            discount_pct=int(data.get('discount_pct', 0)),
            final_price_usd=final_price_usd,
            acknowledged_timing=True,
            notify_when_ready=notify_when_ready,
            title=title or 'Untitled',
            authors=authors if isinstance(authors, list) else [authors] if authors else [],
            abstract=abstract or '',
            workgroup=workgroup,
            layer_id=layer_id,
        )
        db.session.add(order)
        db.session.commit()

        pi = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency='usd',
            metadata={'order_id': order.id},
        )
        order.stripe_payment_intent_id = pi.id
        order.stripe_client_secret = pi.client_secret
        db.session.commit()

        return jsonify({'success': True, 'order_id': order.id, 'client_secret': pi.client_secret})
    except Exception as e:
        current_app.logger.exception('create-payment error')
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/inscribe/stripe-webhook/', methods=['POST'])
def inscribe_stripe_webhook():
    """Handle Stripe payment_intent.succeeded; mark paid, create Submission."""
    try:
        import stripe
        payload = request.get_data()
        sig = request.headers.get('Stripe-Signature', '')
        secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '').strip()
        if not secret:
            return jsonify({'error': 'Webhook not configured'}), 503
        try:
            event = stripe.Webhook.construct_event(payload, sig, secret)
        except Exception as e:
            return jsonify({'error': str(e)}), 400
        if event['type'] != 'payment_intent.succeeded':
            return jsonify({'received': True})
        order_id = event['data']['object'].get('metadata', {}).get('order_id')
        if not order_id:
            return jsonify({'received': True})
        order = InscriptionOrder.query.get(order_id)
        if not order or order.status != 'pending_payment':
            return jsonify({'received': True})
        order.status = 'paid'
        order.paid_at = datetime.utcnow()
        db.session.commit()

        submission_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        submission = Submission(
            draft_name=submission_id,
            title=order.title or 'Untitled',
            authors=order.authors or [],
            abstract=order.abstract or '',
            group=order.workgroup or '',
            layer_id=order.layer_id,
            status='inscription_pending',
            sourceType='ordinal',
            ordinalId=None,
            inscription_order_id=order.id,
            submitted_by='Anonymous User',
        )
        db.session.add(submission)
        db.session.commit()

        return jsonify({'received': True})
    except Exception as e:
        current_app.logger.exception('stripe webhook error')
        return jsonify({'error': str(e)}), 500


@bp.route('/inscribe/<order_id>/status/', methods=['GET'])
def inscribe_order_status(order_id):
    """Return order status + inscription_id when complete."""
    order = InscriptionOrder.query.get(order_id)
    if not order:
        return jsonify({'success': False, 'error': 'Order not found'}), 404
    submission = Submission.query.filter_by(inscription_order_id=order_id).first()
    return jsonify({
        'success': True,
        'status': order.status,
        'inscription_id': order.inscription_id,
        'submission_id': submission.id if submission else None,
        'title': order.title,
        'authors': order.authors,
    })


@bp.route('/inscription/create', methods=['POST'])
def inscription_create():
    """Create Unisat inscription order."""
    try:
        data = request.get_json() or {}
        receive_address = (data.get('receiveAddress') or '').strip()
        files = data.get('files') or []
        fee_rate = float(data.get('feeRate', 10))
        if not receive_address:
            return jsonify({'success': False, 'error': 'Receive address is required'}), 400
        if not files:
            return jsonify({'success': False, 'error': 'At least one file is required'}), 400

        api_key = os.environ.get('UNISAT_API_KEY', '').strip()
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'Inscription service not configured. Set UNISAT_API_KEY to enable.',
                'placeholder': True
            }), 503

        base_url = 'https://open-api-testnet.unisat.io' if os.environ.get('UNISAT_TESTNET') else 'https://open-api.unisat.io'
        url = f'{base_url}/v2/inscribe/order/create'
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        payload = {
            'receiveAddress': receive_address,
            'feeRate': fee_rate,
            'outputValue': 546,
            'files': [{'filename': f.get('filename', 'content.txt'), 'dataURL': f.get('dataURL')} for f in files]
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        result = resp.json()
        if result.get('code') != 1:
            return jsonify({'success': False, 'error': result.get('msg', 'Unisat API error')}), 400
        d = result.get('data', {})
        return jsonify({
            'success': True,
            'order_id': d.get('orderId', ''),
            'pay_address': d.get('payAddress', ''),
            'amount': d.get('amount', 0),
            'qr_code': None
        })
    except requests.RequestException as e:
        return jsonify({'success': False, 'error': f'Unisat API request failed: {str(e)}'}), 502
    except Exception as e:
        current_app.logger.exception('inscription create error')
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/inscription/status/<order_id>', methods=['GET'])
def inscription_status(order_id):
    """Poll Unisat inscription order status."""
    try:
        api_key = os.environ.get('UNISAT_API_KEY', '').strip()
        if not api_key:
            return jsonify({'success': False, 'error': 'Not configured', 'status': 'pending'}), 503
        base_url = 'https://open-api-testnet.unisat.io' if os.environ.get('UNISAT_TESTNET') else 'https://open-api.unisat.io'
        url = f'{base_url}/v2/inscribe/order/{order_id}'
        headers = {'Authorization': f'Bearer {api_key}'}
        resp = requests.get(url, headers=headers, timeout=10)
        result = resp.json()
        if result.get('code') != 1:
            return jsonify({'status': 'pending', 'error': result.get('msg')})
        d = result.get('data', {})
        status = d.get('status', 'pending')
        files = d.get('files', [])
        inscription_id = files[0].get('inscriptionId', '') if files else ''
        if status == 'completed' and inscription_id:
            return jsonify({'success': True, 'status': 'completed', 'inscription_id': inscription_id})
        return jsonify({'status': status, 'inscription_id': inscription_id or None})
    except Exception as e:
        return jsonify({'status': 'pending', 'error': str(e)})


@bp.route('/inscription/btc-price', methods=['GET'])
def inscription_btc_price():
    """Fetch current BTC price in USD."""
    try:
        resp = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd', timeout=5)
        resp.raise_for_status()
        data = resp.json()
        price = data.get('bitcoin', {}).get('usd', 0)
        return jsonify({'success': True, 'usd': price})
    except Exception as e:
        current_app.logger.warning(f'BTC price fetch failed: {e}')
        return jsonify({'success': False, 'usd': 97000})


@bp.route('/inscription/network-fee', methods=['GET'])
def inscription_network_fee():
    """Fetch current Bitcoin network fee rates from mempool.space."""
    try:
        base = 'https://mempool.space/testnet/api' if os.environ.get('UNISAT_TESTNET') else 'https://mempool.space/api'
        url = f'{base}/v1/fees/recommended'
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return jsonify({
            'success': True,
            'fastestFee': data.get('fastestFee', 0),
            'halfHourFee': data.get('halfHourFee', 0),
            'hourFee': data.get('hourFee', 0),
            'economyFee': data.get('economyFee', 0),
            'minimumFee': data.get('minimumFee', 0)
        })
    except Exception as e:
        current_app.logger.warning(f'Network fee fetch failed: {e}')
        return jsonify({
            'success': False,
            'economyFee': 5,
            'hourFee': 10,
            'halfHourFee': 15,
            'fastestFee': 25,
            'minimumFee': 1
        })


@bp.route('/inscription/search-duplicate/text', methods=['POST'])
def inscription_search_duplicate_text():
    """Search for duplicate text content in GovHub submissions."""
    try:
        from services.submission_dedup import find_submission_conflict, hash_text_content

        data = request.get_json() or {}
        text = (data.get('text') or '').strip()
        if not text:
            return jsonify({'found': False})
        content_hash = hash_text_content(text)
        conflict = find_submission_conflict(title='', content_hash=content_hash)
        if conflict:
            _, sub = conflict
            return jsonify({
                'found': True,
                'inscriptionId': getattr(sub, 'ordinalId', None),
                'ml_number': sub.ml_number,
                'title': sub.title,
            })
        return jsonify({'found': False})
    except Exception:
        return jsonify({'found': False, 'message': 'Search unavailable'})


@bp.route('/inscription/search-duplicate/image', methods=['POST'])
def inscription_search_duplicate_image():
    """Search for duplicate binary/image content by hash in GovHub submissions."""
    try:
        from services.submission_dedup import find_submission_conflict, hash_binary_content
        import base64

        data = request.get_json() or {}
        content_hash = (data.get('contentHash') or '').strip().lower()
        if not content_hash and data.get('dataUrl'):
            raw = data['dataUrl']
            if ',' in raw:
                raw = raw.split(',', 1)[1]
            content_hash = hash_binary_content(base64.b64decode(raw))
        if not content_hash:
            return jsonify({'found': False})
        conflict = find_submission_conflict(title='', content_hash=content_hash)
        if conflict:
            _, sub = conflict
            return jsonify({
                'found': True,
                'inscriptionId': getattr(sub, 'ordinalId', None),
                'ml_number': sub.ml_number,
                'title': sub.title,
            })
        return jsonify({'found': False})
    except Exception:
        return jsonify({'found': False, 'message': 'Search unavailable'})


# Page routes for inscription wizard
@bp_pages.route('/immortalize/')
@bp_pages.route('/inscribe/')
@require_auth
def immortalize_redirect():
    """Redirect to submit page Immortalize tab."""
    return redirect('/submit/?tab=immortalize')


@bp_pages.route('/immortalize/success/<order_id>/')
@require_auth
def immortalize_success(order_id):
    """Confirmation page after Stripe payment - shows tentative info and Inscription Pending status."""
    from services.rendering import _format_base_template, generate_user_menu
    from services.identity import get_current_user
    from config import BUILD_NUMBER

    order = InscriptionOrder.query.get(order_id)
    if not order:
        return "Order not found", 404

    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    title = order.title or 'Untitled'
    authors_str = ', '.join(order.authors) if order.authors else ''

    order_module = gh_living_module(
        'Order details',
        f'<h5 class="mb-3">{title}</h5>'
        f'<p class="mb-1"><strong>Authors:</strong> {authors_str}</p>'
        f'<p class="mb-1"><strong>Order ID:</strong> <code>{order_id}</code></p>'
        f'<p class="mb-0"><strong>Status:</strong> <span id="orderStatus">{order.status}</span></p>',
        'fa-receipt',
    )
    content = f'''
<div class="gh-page container mt-4">
    {gh_page_header('Order Confirmed', title, 'fa-check-circle', actions_html='<a href="/submit/" class="btn btn-primary btn-sm">Back to Submit</a>', breadcrumb_html=gh_breadcrumb([('Home', '/'), ('Submit', '/submit/'), ('Order Confirmed', None)]))}
    <div class="alert alert-info mb-3"><span class="badge bg-warning">Inscription Pending</span> Times to receive may vary.</div>
    {order_module}
    <div id="statusPoll"></div>
</div>
<script>
(function() {{
    function poll() {{
        fetch('/api/inscribe/{order_id}/status/')
            .then(r => r.json())
            .then(d => {{
                document.getElementById('orderStatus').textContent = d.status || 'pending';
                const el = document.getElementById('statusPoll');
                if (d.status === 'completed' && d.submission_id) {{
                    el.innerHTML = '<p><a href="/submit/status/' + d.submission_id + '/" class="btn btn-success">View Submission</a></p>';
                    return;
                }}
                setTimeout(poll, 5000);
            }});
    }}
    poll();
}})();
</script>
'''
    return _format_base_template(
        title="Order Confirmed - MLGH",
        theme=current_theme,
        user_menu=user_menu,
        content=content,
        build_number=BUILD_NUMBER,
    )
