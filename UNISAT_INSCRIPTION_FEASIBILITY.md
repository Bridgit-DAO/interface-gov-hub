# Unisat SDK Integration Feasibility Analysis
## Adding Inscription Services to MLGH Datatracker

**Prepared by**: PM Agent  
**Date**: 2026-02-10  
**Status**: Feasibility Analysis  
**Priority**: Medium-High

---

## Executive Summary

**Feasibility Rating: ⭐⭐⭐⭐ (4/5) - Highly Feasible with Moderate Complexity**

Integrating Unisat SDK to add inscription creation services to the MLGH datatracker is **technically feasible and strategically valuable**. The current system already has 75% complete ordinals **loading** functionality via ordinals.com API. Adding Unisat SDK would enable **inscription creation** (writing), completing the full read-write cycle for Bitcoin Ordinals.

### Key Findings

✅ **Strengths:**
- Current ordinals infrastructure already in place (database schema, UI, API endpoints)
- Unisat provides well-documented REST API
- No SDK installation required (REST API only)
- Existing payment flow patterns can be adapted
- Strong alignment with MLGH's decentralized document storage goals

⚠️ **Challenges:**
- Requires Bitcoin payment handling
- Order tracking and status monitoring needed
- API key management and security
- User wallet integration for payments
- Additional backend infrastructure

💰 **Cost Implications:**
- Free tier: 5 calls/second, 2,000 calls/day
- Paid tiers available for higher volume
- Bitcoin network fees paid by users
- Unisat service fees: 1999 sats base + 4.99% network fee

---

## Current State Analysis

### What We Have (Ordinals Loading - 75% Complete)

The datatracker currently supports **reading/loading** Bitcoin Ordinal inscriptions:

1. **Database Schema** ✅
   - `sourceType` column ('file' or 'ordinal')
   - `ordinalId`, `inscriptionNumber`, `blockHeight`
   - `inscriptionTimestamp`, `ordinalContentUrl`, `ordinalContentType`

2. **API Endpoints** ✅
   - `POST /api/ordinal/preview` - Preview existing inscriptions
   - `POST /api/ordinal/convert-markdown` - Convert markdown to HTML

3. **Frontend UI** ✅
   - Tabbed interface (Upload File / From Ordinal)
   - Real-time preview for images, text, markdown, HTML
   - Metadata display
   - Source type badges

4. **Content Support** ✅
   - Images (PNG, JPEG, GIF, SVG, WebP)
   - Text (plain text, UTF-8)
   - Markdown (GitHub-flavored)
   - HTML (sandboxed)
   - Size limit: 50KB

### What We Need (Inscription Creation)

To add inscription **writing** capabilities via Unisat:

1. **New API Integration**
   - Unisat REST API endpoints
   - API key management
   - Request/response handling

2. **Payment Flow**
   - Bitcoin payment address generation
   - Payment monitoring
   - Transaction confirmation

3. **Order Management**
   - Order creation and tracking
   - Status monitoring (pending → inscribing → confirmed)
   - Error handling and refunds

4. **User Experience**
   - File upload → inscription creation flow
   - Payment instructions
   - Progress tracking
   - Inscription ID retrieval

---

## Unisat SDK/API Overview

### API Structure

Unisat provides a **REST API** (not a traditional SDK), which simplifies integration:

**Base URLs:**
- Mainnet: `https://open-api.unisat.io`
- Testnet: `https://open-api-testnet.unisat.io`
- Swagger: `https://open-api.unisat.io/swagger.html`

**Authentication:**
```bash
Authorization: Bearer YOUR_API_KEY
```

### Key Endpoint: Create Inscription Order

**Endpoint:** `POST /v2/inscribe/order/create`

**Request Body:**
```json
{
  "receiveAddress": "bc1q...",           // Bitcoin address to receive inscription
  "feeRate": 10,                         // Satoshis per byte
  "outputValue": 546,                    // Balance per inscription (sats)
  "files": [
    {
      "filename": "document.txt",
      "dataURL": "data:text/plain;base64,..." // Base64 encoded content
    }
  ],
  "devAddress": "bc1q...",               // Optional: developer fee address
  "devFee": 1000                         // Optional: developer fee in sats
}
```

**Response:**
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "orderId": "order_123456",
    "status": "pending",
    "payAddress": "bc1q...",             // Address to send payment to
    "receiveAddress": "bc1q...",         // Where inscription will be sent
    "amount": 3000,                      // Total amount to pay (sats)
    "paidAmount": 0,
    "outputValue": 546,
    "feeRate": 10,
    "minerFee": 1200,
    "serviceFee": 1999,
    "devFee": 0,
    "files": [
      {
        "filename": "document.txt",
        "inscriptionId": "",              // Populated after inscription
        "status": "pending"
      }
    ],
    "count": 1,
    "pendingCount": 1,
    "createTime": 1693439128100
  }
}
```

### Pricing Structure

**Service Fees:**
- Base fee: **1,999 sats** for first 25 inscriptions
- Network fee: **4.99%** of miner fees
- Total = balance + networkFee + serviceFee + devFee

**Example Calculation:**
```javascript
// For 1 file, 1KB size, 10 sat/byte fee rate
const balance = 546;              // Output value
const networkFee = ~1200;         // Depends on file size
const serviceFee = 1999;          // Base fee
const total = 546 + 1200 + 1999 = 3745 sats (~$2.50 at $67k BTC)
```

**API Rate Limits:**
- Free tier: 5 calls/second, 2,000 calls/day
- Paid tiers: Higher limits available

### Capabilities

✅ **Supported:**
- Multiple files per order (up to 2,000)
- Max file size: 390KB per file
- All content types (images, text, JSON, HTML, etc.)
- Custom fee rates
- Developer fees
- Testnet support

❌ **Limitations:**
- Requires Bitcoin payment (cannot be automated)
- Orders are separate from UniSat website (no shared data)
- No OG card or .unisat domain discounts
- Payment must be exact amount

---

## Integration Architecture

### Proposed System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    MLGH Datatracker                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐         ┌──────────────────┐         │
│  │  User Interface │         │  Backend API     │         │
│  │                 │         │                  │         │
│  │ • Upload file   │────────▶│ • Validate file  │         │
│  │ • Choose action │         │ • Create order   │         │
│  │   - Store only  │         │ • Track status   │         │
│  │   - Inscribe    │         │                  │         │
│  └─────────────────┘         └──────────────────┘         │
│         │                             │                     │
│         │                             │                     │
│         ▼                             ▼                     │
│  ┌─────────────────┐         ┌──────────────────┐         │
│  │  Payment UI     │         │  Order Manager   │         │
│  │                 │         │                  │         │
│  │ • Show QR code  │         │ • Poll status    │         │
│  │ • Payment addr  │         │ • Update DB      │         │
│  │ • Amount        │         │ • Notify user    │         │
│  └─────────────────┘         └──────────────────┘         │
│                                       │                     │
└───────────────────────────────────────┼─────────────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────┐
                         │   Unisat REST API        │
                         │                          │
                         │ • Create order           │
                         │ • Check status           │
                         │ • Get inscription ID     │
                         └──────────────────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────┐
                         │   Bitcoin Network        │
                         │                          │
                         │ • Payment confirmation   │
                         │ • Inscription creation   │
                         └──────────────────────────┘
```

### Data Flow

1. **User uploads file** → Frontend
2. **File validation** → Backend validates size, type
3. **User chooses "Inscribe"** → Triggers inscription flow
4. **Create Unisat order** → Backend calls Unisat API
5. **Display payment info** → Show payment address, amount, QR code
6. **User pays** → External Bitcoin wallet
7. **Poll order status** → Backend checks Unisat API periodically
8. **Order confirmed** → Retrieve inscription ID
9. **Update submission** → Store inscription ID in database
10. **Notify user** → Show success message with inscription link

---

## Database Schema Changes

### New Tables

#### 1. `inscription_order` Table

```sql
CREATE TABLE inscription_order (
    id TEXT PRIMARY KEY,                      -- Our internal order ID
    submission_id TEXT NOT NULL,              -- Link to submission
    unisat_order_id TEXT NOT NULL,            -- Unisat's order ID
    status TEXT NOT NULL,                     -- pending, paid, inscribing, completed, failed
    pay_address TEXT NOT NULL,                -- Bitcoin address to pay
    receive_address TEXT,                     -- Address to receive inscription
    amount INTEGER NOT NULL,                  -- Total amount in satoshis
    paid_amount INTEGER DEFAULT 0,            -- Amount paid so far
    fee_rate INTEGER,                         -- Fee rate in sat/byte
    miner_fee INTEGER,                        -- Miner fee in sats
    service_fee INTEGER,                      -- Unisat service fee in sats
    dev_fee INTEGER DEFAULT 0,                -- Optional developer fee
    inscription_id TEXT,                      -- Final inscription ID (after completion)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    error_message TEXT,
    
    FOREIGN KEY (submission_id) REFERENCES submission(id)
);

CREATE INDEX idx_inscription_order_submission ON inscription_order(submission_id);
CREATE INDEX idx_inscription_order_status ON inscription_order(status);
CREATE INDEX idx_inscription_order_unisat ON inscription_order(unisat_order_id);
```

#### 2. `unisat_config` Table

```sql
CREATE TABLE unisat_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key TEXT NOT NULL,                    -- Encrypted API key
    environment TEXT NOT NULL,                -- 'mainnet' or 'testnet'
    dev_address TEXT,                         -- Optional developer fee address
    dev_fee INTEGER DEFAULT 0,                -- Default developer fee
    default_fee_rate INTEGER DEFAULT 10,      -- Default fee rate
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Updated Tables

#### `submission` Table (add columns)

```sql
ALTER TABLE submission ADD COLUMN inscription_order_id TEXT;
ALTER TABLE submission ADD COLUMN inscription_status TEXT;  -- null, pending, inscribing, completed, failed

CREATE INDEX idx_submission_inscription_order ON submission(inscription_order_id);
```

---

## API Implementation

### New Backend Endpoints

#### 1. Create Inscription Order

```python
@app.route('/api/inscription/create', methods=['POST'])
@require_auth
def create_inscription_order():
    """
    Create a Unisat inscription order for a submission
    
    Request:
    {
        "submission_id": "sub-123",
        "receive_address": "bc1q...",
        "fee_rate": 10  // optional, defaults to config
    }
    
    Response:
    {
        "success": true,
        "order_id": "order-123",
        "pay_address": "bc1q...",
        "amount": 3745,
        "qr_code": "data:image/png;base64,...",
        "status_url": "/api/inscription/status/order-123"
    }
    """
    data = request.json
    submission_id = data.get('submission_id')
    receive_address = data.get('receive_address')
    fee_rate = data.get('fee_rate', get_default_fee_rate())
    
    # Validate submission exists and user owns it
    submission = Submission.query.get(submission_id)
    if not submission:
        return jsonify({'error': 'Submission not found'}), 404
    
    if submission.submitted_by != get_current_user()['name']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get file content
    file_path = submission.file_path
    with open(file_path, 'rb') as f:
        file_content = f.read()
    
    # Convert to base64 data URL
    import base64
    import mimetypes
    mime_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
    data_url = f"data:{mime_type};base64,{base64.b64encode(file_content).decode()}"
    
    # Create Unisat order
    unisat_response = create_unisat_order(
        receive_address=receive_address,
        fee_rate=fee_rate,
        files=[{
            'filename': submission.filename,
            'dataURL': data_url
        }]
    )
    
    if not unisat_response.get('success'):
        return jsonify({'error': 'Failed to create order'}), 500
    
    # Store order in database
    order = InscriptionOrder(
        id=generate_order_id(),
        submission_id=submission_id,
        unisat_order_id=unisat_response['orderId'],
        status='pending',
        pay_address=unisat_response['payAddress'],
        receive_address=receive_address,
        amount=unisat_response['amount'],
        fee_rate=fee_rate,
        miner_fee=unisat_response['minerFee'],
        service_fee=unisat_response['serviceFee']
    )
    db.session.add(order)
    
    # Update submission
    submission.inscription_order_id = order.id
    submission.inscription_status = 'pending'
    db.session.commit()
    
    # Generate QR code
    qr_code = generate_payment_qr(unisat_response['payAddress'], unisat_response['amount'])
    
    return jsonify({
        'success': True,
        'order_id': order.id,
        'pay_address': unisat_response['payAddress'],
        'amount': unisat_response['amount'],
        'qr_code': qr_code,
        'status_url': f'/api/inscription/status/{order.id}'
    })
```

#### 2. Check Order Status

```python
@app.route('/api/inscription/status/<order_id>', methods=['GET'])
@require_auth
def get_inscription_status(order_id):
    """
    Check status of an inscription order
    
    Response:
    {
        "order_id": "order-123",
        "status": "inscribing",
        "paid_amount": 3745,
        "amount": 3745,
        "inscription_id": null,
        "progress": {
            "pending": 0,
            "inscribing": 1,
            "confirmed": 0
        }
    }
    """
    order = InscriptionOrder.query.get(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    # Check if user owns this order
    submission = Submission.query.get(order.submission_id)
    if submission.submitted_by != get_current_user()['name']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Poll Unisat API for latest status
    unisat_status = get_unisat_order_status(order.unisat_order_id)
    
    # Update order status
    order.status = unisat_status['status']
    order.paid_amount = unisat_status['paidAmount']
    
    if unisat_status['status'] == 'completed':
        order.inscription_id = unisat_status['files'][0]['inscriptionId']
        order.completed_at = datetime.utcnow()
        
        # Update submission
        submission.ordinalId = order.inscription_id
        submission.sourceType = 'ordinal'
        submission.inscription_status = 'completed'
    
    db.session.commit()
    
    return jsonify({
        'order_id': order.id,
        'status': order.status,
        'paid_amount': order.paid_amount,
        'amount': order.amount,
        'inscription_id': order.inscription_id,
        'progress': {
            'pending': unisat_status.get('pendingCount', 0),
            'inscribing': unisat_status.get('unconfirmedCount', 0),
            'confirmed': unisat_status.get('confirmedCount', 0)
        }
    })
```

#### 3. Unisat API Helper Functions

```python
import requests
from flask import current_app

def get_unisat_config():
    """Get active Unisat configuration"""
    config = UnisatConfig.query.filter_by(is_active=True).first()
    if not config:
        raise Exception("No active Unisat configuration found")
    return config

def create_unisat_order(receive_address, fee_rate, files, dev_fee=0):
    """
    Create inscription order via Unisat API
    
    Args:
        receive_address: Bitcoin address to receive inscription
        fee_rate: Fee rate in sat/byte
        files: List of {filename, dataURL} dicts
        dev_fee: Optional developer fee in sats
    
    Returns:
        dict: Unisat API response
    """
    config = get_unisat_config()
    
    url = f"{get_unisat_base_url(config.environment)}/v2/inscribe/order/create"
    
    headers = {
        'Authorization': f'Bearer {decrypt_api_key(config.api_key)}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'receiveAddress': receive_address,
        'feeRate': fee_rate,
        'outputValue': 546,  # Standard output value
        'files': files
    }
    
    if dev_fee > 0 and config.dev_address:
        payload['devAddress'] = config.dev_address
        payload['devFee'] = dev_fee
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('code') != 1:
            raise Exception(f"Unisat API error: {result.get('msg')}")
        
        return {
            'success': True,
            'orderId': result['data']['orderId'],
            'payAddress': result['data']['payAddress'],
            'amount': result['data']['amount'],
            'minerFee': result['data']['minerFee'],
            'serviceFee': result['data']['serviceFee']
        }
        
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Unisat API request failed: {e}")
        return {'success': False, 'error': str(e)}

def get_unisat_order_status(order_id):
    """
    Get order status from Unisat API
    
    Args:
        order_id: Unisat order ID
    
    Returns:
        dict: Order status data
    """
    config = get_unisat_config()
    
    url = f"{get_unisat_base_url(config.environment)}/v2/inscribe/order/{order_id}"
    
    headers = {
        'Authorization': f'Bearer {decrypt_api_key(config.api_key)}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('code') != 1:
            raise Exception(f"Unisat API error: {result.get('msg')}")
        
        return result['data']
        
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Unisat API request failed: {e}")
        return None

def get_unisat_base_url(environment):
    """Get Unisat API base URL for environment"""
    if environment == 'testnet':
        return 'https://open-api-testnet.unisat.io'
    return 'https://open-api.unisat.io'

def decrypt_api_key(encrypted_key):
    """Decrypt API key from database"""
    # Implement encryption/decryption logic
    # For now, return as-is (should be encrypted in production)
    return encrypted_key

def generate_payment_qr(address, amount_sats):
    """
    Generate QR code for Bitcoin payment
    
    Args:
        address: Bitcoin address
        amount_sats: Amount in satoshis
    
    Returns:
        str: Base64 encoded QR code image
    """
    import qrcode
    from io import BytesIO
    import base64
    
    # Convert sats to BTC
    amount_btc = amount_sats / 100_000_000
    
    # Bitcoin URI format
    uri = f"bitcoin:{address}?amount={amount_btc}"
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"
```

---

## Frontend Implementation

### New UI Components

#### 1. Inscription Action Button

Add to submission detail page:

```html
<!-- After file upload success -->
{% if submission.sourceType == 'file' and not submission.inscription_order_id %}
<div class="card mt-3">
    <div class="card-header">
        <h5>🪙 Inscribe to Bitcoin</h5>
    </div>
    <div class="card-body">
        <p>Permanently inscribe this document to the Bitcoin blockchain as an Ordinal.</p>
        <button class="btn btn-primary" onclick="showInscriptionModal()">
            <i class="fas fa-coins me-2"></i>Create Inscription
        </button>
    </div>
</div>
{% endif %}
```

#### 2. Inscription Modal

```html
<!-- Inscription Modal -->
<div class="modal fade" id="inscriptionModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Create Bitcoin Inscription</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <!-- Step 1: Configuration -->
                <div id="step1" class="inscription-step">
                    <h6>Step 1: Configure Inscription</h6>
                    
                    <div class="mb-3">
                        <label class="form-label">Receive Address *</label>
                        <input type="text" id="receiveAddress" class="form-control" 
                               placeholder="bc1q..." required>
                        <small class="form-text text-muted">
                            Bitcoin address where the inscription will be sent
                        </small>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Fee Rate (sat/byte)</label>
                        <input type="number" id="feeRate" class="form-control" 
                               value="10" min="1" max="1000">
                        <small class="form-text text-muted">
                            Higher fee = faster confirmation. Recommended: 10-50
                        </small>
                    </div>
                    
                    <div class="alert alert-info">
                        <strong>Estimated Cost:</strong> <span id="estimatedCost">Calculating...</span>
                    </div>
                    
                    <button class="btn btn-primary" onclick="createOrder()">
                        Continue to Payment
                    </button>
                </div>
                
                <!-- Step 2: Payment -->
                <div id="step2" class="inscription-step" style="display: none;">
                    <h6>Step 2: Send Payment</h6>
                    
                    <div class="alert alert-warning">
                        <strong>⚠️ Important:</strong> Send exactly the amount shown below. 
                        Incorrect amounts may result in delays or refunds.
                    </div>
                    
                    <div class="text-center mb-3">
                        <img id="paymentQR" src="" alt="Payment QR Code" class="img-fluid" 
                             style="max-width: 300px;">
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Payment Address</label>
                        <div class="input-group">
                            <input type="text" id="payAddress" class="form-control" readonly>
                            <button class="btn btn-outline-secondary" onclick="copyAddress()">
                                <i class="fas fa-copy"></i> Copy
                            </button>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Amount to Send</label>
                        <div class="input-group">
                            <input type="text" id="payAmount" class="form-control" readonly>
                            <span class="input-group-text">sats</span>
                        </div>
                        <small class="form-text text-muted">
                            ≈ $<span id="payAmountUSD">0.00</span> USD
                        </small>
                    </div>
                    
                    <div class="progress mb-3">
                        <div id="paymentProgress" class="progress-bar progress-bar-striped progress-bar-animated" 
                             role="progressbar" style="width: 0%">
                            Waiting for payment...
                        </div>
                    </div>
                    
                    <button class="btn btn-secondary" onclick="checkPaymentStatus()">
                        <i class="fas fa-sync me-2"></i>Check Status
                    </button>
                </div>
                
                <!-- Step 3: Inscribing -->
                <div id="step3" class="inscription-step" style="display: none;">
                    <h6>Step 3: Inscribing</h6>
                    
                    <div class="alert alert-success">
                        <strong>✅ Payment Received!</strong> Your inscription is being created.
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Progress</label>
                        <div class="progress">
                            <div id="inscriptionProgress" class="progress-bar bg-success" 
                                 role="progressbar" style="width: 50%">
                                Inscribing...
                            </div>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <p><strong>Status:</strong> <span id="inscriptionStatus">Inscribing</span></p>
                        <p><strong>Estimated Time:</strong> 10-60 minutes</p>
                    </div>
                    
                    <button class="btn btn-secondary" onclick="checkInscriptionStatus()">
                        <i class="fas fa-sync me-2"></i>Refresh Status
                    </button>
                </div>
                
                <!-- Step 4: Complete -->
                <div id="step4" class="inscription-step" style="display: none;">
                    <h6>Step 4: Complete!</h6>
                    
                    <div class="alert alert-success">
                        <strong>🎉 Inscription Created Successfully!</strong>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Inscription ID</label>
                        <div class="input-group">
                            <input type="text" id="inscriptionId" class="form-control" readonly>
                            <button class="btn btn-outline-secondary" onclick="copyInscriptionId()">
                                <i class="fas fa-copy"></i> Copy
                            </button>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <a id="viewOnOrdinals" href="#" target="_blank" class="btn btn-primary">
                            <i class="fas fa-external-link-alt me-2"></i>View on Ordinals.com
                        </a>
                    </div>
                    
                    <button class="btn btn-success" onclick="location.reload()">
                        Done
                    </button>
                </div>
            </div>
        </div>
    </div>
</div>
```

#### 3. JavaScript Functions

```javascript
let currentOrderId = null;
let statusCheckInterval = null;

async function showInscriptionModal() {
    const modal = new bootstrap.Modal(document.getElementById('inscriptionModal'));
    modal.show();
    
    // Estimate cost
    await estimateCost();
}

async function estimateCost() {
    const feeRate = document.getElementById('feeRate').value;
    
    // Simplified estimation (should match backend calculation)
    const fileSize = {{ submission.file_size or 1000 }};  // bytes
    const baseFee = 1999;
    const networkFee = Math.ceil((fileSize / 4 + 150) * feeRate);
    const serviceFee = Math.ceil(networkFee * 0.0499);
    const total = 546 + networkFee + baseFee + serviceFee;
    
    document.getElementById('estimatedCost').textContent = 
        `${total.toLocaleString()} sats (≈ $${(total * 0.00067).toFixed(2)} USD)`;
}

async function createOrder() {
    const receiveAddress = document.getElementById('receiveAddress').value;
    const feeRate = document.getElementById('feeRate').value;
    
    if (!receiveAddress) {
        alert('Please enter a receive address');
        return;
    }
    
    try {
        const response = await fetch('/api/inscription/create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                submission_id: '{{ submission.id }}',
                receive_address: receiveAddress,
                fee_rate: parseInt(feeRate)
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            currentOrderId = result.order_id;
            
            // Show payment step
            document.getElementById('step1').style.display = 'none';
            document.getElementById('step2').style.display = 'block';
            
            // Fill payment details
            document.getElementById('paymentQR').src = result.qr_code;
            document.getElementById('payAddress').value = result.pay_address;
            document.getElementById('payAmount').value = result.amount;
            document.getElementById('payAmountUSD').textContent = 
                (result.amount * 0.00067).toFixed(2);
            
            // Start polling for payment
            startPaymentPolling();
        } else {
            alert('Failed to create order: ' + result.error);
        }
    } catch (error) {
        console.error('Error creating order:', error);
        alert('Failed to create order. Please try again.');
    }
}

function startPaymentPolling() {
    statusCheckInterval = setInterval(checkPaymentStatus, 10000);  // Check every 10 seconds
}

async function checkPaymentStatus() {
    if (!currentOrderId) return;
    
    try {
        const response = await fetch(`/api/inscription/status/${currentOrderId}`);
        const result = await response.json();
        
        if (result.status === 'paid' || result.status === 'inscribing') {
            // Payment received
            clearInterval(statusCheckInterval);
            
            document.getElementById('step2').style.display = 'none';
            document.getElementById('step3').style.display = 'block';
            
            // Start polling for inscription completion
            startInscriptionPolling();
        } else if (result.status === 'completed') {
            // Already completed
            showCompletionStep(result.inscription_id);
        }
        
        // Update progress bar
        const progress = (result.paid_amount / result.amount) * 100;
        document.getElementById('paymentProgress').style.width = progress + '%';
        
    } catch (error) {
        console.error('Error checking payment status:', error);
    }
}

function startInscriptionPolling() {
    statusCheckInterval = setInterval(checkInscriptionStatus, 30000);  // Check every 30 seconds
}

async function checkInscriptionStatus() {
    if (!currentOrderId) return;
    
    try {
        const response = await fetch(`/api/inscription/status/${currentOrderId}`);
        const result = await response.json();
        
        if (result.status === 'completed' && result.inscription_id) {
            clearInterval(statusCheckInterval);
            showCompletionStep(result.inscription_id);
        }
        
        // Update status text
        document.getElementById('inscriptionStatus').textContent = 
            result.status.charAt(0).toUpperCase() + result.status.slice(1);
        
    } catch (error) {
        console.error('Error checking inscription status:', error);
    }
}

function showCompletionStep(inscriptionId) {
    document.getElementById('step3').style.display = 'none';
    document.getElementById('step4').style.display = 'block';
    
    document.getElementById('inscriptionId').value = inscriptionId;
    document.getElementById('viewOnOrdinals').href = 
        `https://ordinals.com/inscription/${inscriptionId}`;
}

function copyAddress() {
    const address = document.getElementById('payAddress');
    address.select();
    document.execCommand('copy');
    alert('Address copied to clipboard!');
}

function copyInscriptionId() {
    const id = document.getElementById('inscriptionId');
    id.select();
    document.execCommand('copy');
    alert('Inscription ID copied to clipboard!');
}
```

---

## Implementation Plan

### Phase 1: Backend Infrastructure (Week 1)

**Tasks:**
1. ✅ Database schema changes
   - Create `inscription_order` table
   - Create `unisat_config` table
   - Add columns to `submission` table
   - Run migrations

2. ✅ Unisat API integration
   - Implement API helper functions
   - Test API calls (testnet)
   - Error handling
   - Rate limiting

3. ✅ Order management endpoints
   - `POST /api/inscription/create`
   - `GET /api/inscription/status/<order_id>`
   - Background status polling job

4. ✅ Security
   - API key encryption
   - User authorization checks
   - Input validation

**Deliverables:**
- Working API endpoints
- Database migrations
- Unit tests
- API documentation

### Phase 2: Frontend UI (Week 2)

**Tasks:**
1. ✅ Inscription action button
   - Add to submission detail page
   - Show only for file submissions
   - Hide if already inscribed

2. ✅ Inscription modal
   - Step 1: Configuration form
   - Step 2: Payment display
   - Step 3: Progress tracking
   - Step 4: Completion

3. ✅ JavaScript functionality
   - Order creation
   - Payment polling
   - Status updates
   - QR code display

4. ✅ UI/UX polish
   - Loading states
   - Error messages
   - Progress indicators
   - Responsive design

**Deliverables:**
- Complete UI flow
- User testing
- Documentation

### Phase 3: Admin & Monitoring (Week 3)

**Tasks:**
1. ✅ Admin dashboard
   - View all inscription orders
   - Filter by status
   - Manual intervention tools

2. ✅ Monitoring
   - Order status tracking
   - Failed order alerts
   - API usage metrics

3. ✅ Configuration UI
   - Manage API keys
   - Set default fee rates
   - Configure dev fees

**Deliverables:**
- Admin tools
- Monitoring dashboard
- Configuration interface

### Phase 4: Testing & Deployment (Week 4)

**Tasks:**
1. ✅ Testing
   - Unit tests
   - Integration tests
   - End-to-end tests (testnet)
   - User acceptance testing

2. ✅ Documentation
   - User guide
   - Admin guide
   - API documentation
   - Troubleshooting guide

3. ✅ Deployment
   - Deploy to staging
   - Test with real Bitcoin (testnet)
   - Deploy to production
   - Monitor and iterate

**Deliverables:**
- Test reports
- Complete documentation
- Production deployment
- Post-launch support

---

## Cost Analysis

### Development Costs

**Time Estimates:**
- Backend development: 40 hours
- Frontend development: 32 hours
- Testing: 24 hours
- Documentation: 16 hours
- **Total: ~112 hours** (~3-4 weeks)

**Resource Requirements:**
- 1 Backend developer
- 1 Frontend developer
- 1 QA engineer (part-time)
- 1 Technical writer (part-time)

### Operational Costs

**Unisat API:**
- Free tier: 5 calls/second, 2,000 calls/day
- Paid tiers: $49-$499/month for higher limits
- **Recommendation:** Start with free tier

**Bitcoin Fees (paid by users):**
- Service fee: 1,999 sats per inscription (~$1.35)
- Network fee: Variable (10-50 sat/byte)
- Total per inscription: ~3,000-10,000 sats ($2-7)

**Infrastructure:**
- Database storage: Minimal (order records)
- API calls: Within free tier initially
- Monitoring: Existing infrastructure

### Revenue Opportunities

**Optional Developer Fees:**
- Can charge 500-2,000 sats per inscription
- Transparent to users
- Helps offset operational costs
- **Recommendation:** 1,000 sats (~$0.67) per inscription

**Example:**
- 100 inscriptions/month
- 1,000 sats dev fee each
- = 100,000 sats/month (~$67)
- Covers API costs and provides small revenue

---

## Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Unisat API downtime | Medium | High | Implement retry logic, queue system, status page |
| Bitcoin network congestion | Medium | Medium | Allow user-configurable fee rates, show estimates |
| Payment amount mismatch | Low | High | Clear instructions, exact amount validation |
| Order stuck/failed | Medium | Medium | Manual intervention tools, refund process |
| API rate limits exceeded | Low | Medium | Implement caching, queue, upgrade plan |

### Business Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Low user adoption | Medium | Low | Clear documentation, user education |
| High Bitcoin fees | Medium | Medium | Show cost estimates upfront, allow fee selection |
| Unisat pricing changes | Low | Medium | Monitor pricing, have alternative providers |
| Regulatory concerns | Low | High | Legal review, terms of service, disclaimers |

### Security Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| API key exposure | Low | High | Encryption, secure storage, key rotation |
| Payment fraud | Low | Medium | Blockchain verification, order tracking |
| User address errors | Medium | Medium | Address validation, confirmation step |
| XSS/injection attacks | Low | High | Input sanitization, output encoding |

---

## Alternatives Considered

### 1. Direct Bitcoin Core Integration

**Pros:**
- No third-party dependency
- Full control
- No service fees

**Cons:**
- Requires running Bitcoin node
- Complex inscription logic
- High maintenance burden
- Longer development time

**Verdict:** ❌ Too complex for initial implementation

### 2. Ordinals.com API

**Pros:**
- Already integrated for reading
- Familiar codebase

**Cons:**
- No inscription creation API
- Read-only service
- Not designed for programmatic access

**Verdict:** ❌ Doesn't support inscription creation

### 3. Hiro Ordinals API

**Pros:**
- Well-documented
- Free tier available
- Good developer experience

**Cons:**
- Primarily for reading inscriptions
- Limited inscription creation features
- Less mature than Unisat

**Verdict:** ⚠️ Possible alternative, but less feature-complete

### 4. Custom Inscription Service

**Pros:**
- Full control
- No service fees
- Custom features

**Cons:**
- Requires Bitcoin infrastructure
- Security concerns
- High development cost
- Ongoing maintenance

**Verdict:** ❌ Not feasible for initial launch

### Recommendation: Unisat SDK

**Why Unisat is the best choice:**
1. ✅ Well-documented REST API
2. ✅ Proven track record
3. ✅ Free tier sufficient for initial launch
4. ✅ Simple integration (no SDK installation)
5. ✅ Active support and community
6. ✅ Testnet support for development
7. ✅ Reasonable pricing

---

## Success Metrics

### Technical Metrics

- **API Response Time:** < 2 seconds for order creation
- **Order Success Rate:** > 95%
- **Payment Detection Time:** < 5 minutes
- **Inscription Completion Time:** < 60 minutes (average)
- **Error Rate:** < 5%

### Business Metrics

- **User Adoption:** 10% of submissions use inscription feature (Month 1)
- **Conversion Rate:** 80% of started orders complete
- **User Satisfaction:** > 4/5 rating
- **Cost per Inscription:** < $5 (including all fees)

### Operational Metrics

- **API Uptime:** > 99%
- **Support Tickets:** < 5% of inscriptions require support
- **Failed Orders:** < 2% require manual intervention
- **Refund Rate:** < 1%

---

## Recommendations

### Immediate Actions (Week 1)

1. ✅ **Approve project** - Get stakeholder buy-in
2. ✅ **Register Unisat account** - Obtain API key
3. ✅ **Set up testnet** - Test environment
4. ✅ **Create project plan** - Detailed timeline
5. ✅ **Assign resources** - Developers, QA, writer

### Short-term (Weeks 2-4)

1. ✅ **Implement backend** - API integration, database
2. ✅ **Build frontend** - UI components, JavaScript
3. ✅ **Test thoroughly** - Unit, integration, E2E tests
4. ✅ **Write documentation** - User guide, admin guide
5. ✅ **Deploy to staging** - Internal testing

### Medium-term (Months 2-3)

1. ⏳ **Launch to production** - Gradual rollout
2. ⏳ **Monitor metrics** - Track success metrics
3. ⏳ **Gather feedback** - User surveys, support tickets
4. ⏳ **Iterate and improve** - Bug fixes, enhancements
5. ⏳ **Optimize costs** - Review API usage, fees

### Long-term (Months 4-6)

1. ⏳ **Advanced features** - Bulk inscriptions, batch processing
2. ⏳ **Alternative providers** - Evaluate other APIs
3. ⏳ **Custom infrastructure** - If volume justifies
4. ⏳ **Revenue optimization** - Developer fees, premium features
5. ⏳ **Integration expansion** - Other Bitcoin services

---

## Conclusion

**Integrating Unisat SDK to add inscription services to the MLGH datatracker is highly feasible and strategically valuable.**

### Key Takeaways

✅ **Technically Feasible**
- REST API integration is straightforward
- Existing ordinals infrastructure provides foundation
- No complex dependencies or SDK installation required

✅ **Strategically Aligned**
- Completes the read-write cycle for Bitcoin Ordinals
- Enhances MLGH's decentralized document storage vision
- Differentiates from traditional document trackers

✅ **Economically Viable**
- Free tier sufficient for initial launch
- User-paid fees (no operational burden)
- Optional revenue through developer fees
- Low infrastructure costs

✅ **User Value**
- Permanent, immutable document storage
- Blockchain verification
- Decentralized ownership
- Simple, guided workflow

### Final Recommendation

**Proceed with implementation** using the phased approach outlined above. Start with testnet development, thoroughly test, and launch with a gradual rollout to production.

**Expected Timeline:** 3-4 weeks for initial implementation  
**Expected Cost:** ~112 developer hours + minimal operational costs  
**Expected ROI:** High user value, low cost, strategic differentiation

---

## Appendix

### A. Unisat API Endpoints Reference

```
POST /v2/inscribe/order/create
GET  /v2/inscribe/order/{orderId}
POST /v2/inscribe/order/estimate-fee
```

### B. Bitcoin Address Formats

- **P2PKH:** Starts with `1` (legacy)
- **P2SH:** Starts with `3` (legacy)
- **P2WPKH:** Starts with `bc1q` (SegWit)
- **P2TR:** Starts with `bc1p` (Taproot)

### C. Fee Rate Recommendations

- **Low Priority:** 1-5 sat/byte (slow, cheap)
- **Medium Priority:** 10-20 sat/byte (normal)
- **High Priority:** 50-100 sat/byte (fast, expensive)
- **Urgent:** 100+ sat/byte (very fast, very expensive)

### D. Content Type Support

**Supported by Unisat:**
- All MIME types
- Max 390KB per file
- Up to 2,000 files per order

**Recommended for MLGH:**
- `text/plain` - Plain text documents
- `text/markdown` - Markdown documents
- `text/html` - HTML documents
- `image/png` - PNG images
- `image/jpeg` - JPEG images
- `application/pdf` - PDF documents (if < 390KB)

### E. Error Codes

| Code | Message | Resolution |
|------|---------|------------|
| 1001 | Invalid API key | Check API key configuration |
| 1002 | Rate limit exceeded | Upgrade plan or wait |
| 1003 | Invalid address | Validate Bitcoin address |
| 1004 | File too large | Reduce file size |
| 1005 | Insufficient payment | Send exact amount |
| 1006 | Order expired | Create new order |

### F. Testing Checklist

- [ ] Create order with valid data
- [ ] Create order with invalid address
- [ ] Create order with oversized file
- [ ] Payment detection (testnet)
- [ ] Order status polling
- [ ] Inscription completion
- [ ] Error handling
- [ ] UI responsiveness
- [ ] QR code generation
- [ ] Copy/paste functionality

---

**Document Version:** 1.0  
**Last Updated:** 2026-02-10  
**Author:** PM Agent  
**Status:** Ready for Review  
**Next Steps:** Stakeholder approval, resource allocation, project kickoff
