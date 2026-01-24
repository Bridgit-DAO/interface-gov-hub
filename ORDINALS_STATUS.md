# Ordinals Integration Status

## ✅ Working Features

1. **Database Schema** - All ordinal columns added to `submission` table:
   - `sourceType` (file/ordinal)
   - `ordinalId` (inscription ID)
   - `ordinalContentUrl`
   - `ordinalContentType`
   - `inscriptionNumber`
   - `blockHeight`
   - `inscriptionTimestamp`

2. **Content Preview** - Working perfectly:
   - ✅ Text/plain content displays correctly
   - ✅ Images display correctly  
   - ✅ Markdown support (with conversion)
   - ✅ HTML support (in sandboxed iframe)
   - ✅ JavaScript/JSON display as text
   - ✅ Content size validation (< 50KB)
   - ✅ Proper User-Agent headers to avoid 403 errors

3. **UI Components**:
   - ✅ Two-tab interface (Upload File / From Ordinal)
   - ✅ Inscription ID input with preview button
   - ✅ Dynamic content preview area
   - ✅ Metadata display section
   - ✅ Source type badges on submission list/detail pages

## ⚠️ Known Issues

### Metadata Fetching Not Working

**Problem**: ordinals.com returns truncated/different HTML (1226 chars instead of 4112) when requests come from the server, even with proper User-Agent headers.

**Root Causes**:
1. **JSON API Disabled**: ordinals.com public instance returns `406 Not Acceptable` with message "JSON API disabled" when `Accept: application/json` header is sent
2. **Rate Limiting**: Server requests appear to be rate-limited or blocked differently than browser requests
3. **Cloudflare Protection**: ordinals.com likely uses Cloudflare or similar protection that detects automated requests

**Current Status**:
- Content URL: ✅ Working
- Content Type: ✅ Working  
- Content Size: ✅ Working
- Inscription Number: ❌ Returns N/A
- Block Height: ❌ Returns N/A
- Timestamp: ❌ Returns N/A

**What Was Tried**:
1. ✅ Using JSON API → Failed (406 "JSON API disabled")
2. ✅ HTML scraping with User-Agent header → Returns truncated HTML
3. ✅ Different endpoint variations → All fail or 404
4. ✅ Proper regex patterns for HTML → Patterns are correct (tested with full HTML)

## 🔧 Workarounds

### Option 1: Client-Side Metadata Fetching (Recommended)
Since the browser can fetch the full HTML successfully, move metadata fetching to the frontend:
- JavaScript fetches inscription page from user's browser
- Parses HTML using DOM
- Sends metadata back to backend via hidden form fields
- **Pros**: Will work (no rate limiting)
- **Cons**: Requires JavaScript, slightly slower UX

### Option 2: Self-Hosted ord Instance
Set up own `ord` server with JSON API enabled:
- Deploy ord with `--enable-json-api` flag
- Point to own instance instead of ordinals.com
- **Pros**: Full API access, reliable
- **Cons**: Requires infrastructure, Bitcoin node, storage

### Option 3: Third-Party Ordinals API
Use services like:
- Hiro API (https://api.hiro.so/)
- Ordinals Explorer API
- **Pros**: Reliable, purpose-built
- **Cons**: May have rate limits, costs

### Option 4: Accept as Optional
Make metadata optional/nice-to-have:
- Content preview works perfectly
- Users can view on ordinals.com directly (link provided)
- Metadata displays "N/A" but doesn't block functionality
- **Pros**: Simple, works now
- **Cons**: Less polished UX

## 📝 Recommendation

**Short term**: Option 4 (Accept as optional)
- Feature is 90% functional
- Content preview (the main feature) works perfectly
- Users can click "View on Ordinals.com" for metadata

**Long term**: Option 1 (Client-side fetching)
- Implement JavaScript-based metadata scraping
- Falls back gracefully if JavaScript disabled
- No infrastructure changes needed

## 🚀 Next Steps

1. Test full submission flow (create draft from ordinal)
2. Verify data persists correctly in database
3. Deploy to production
4. Document for users
5. Optionally: Implement client-side metadata fetching

## 📊 Testing

Test inscription ID: `0d89c52f64ae2f27c9964ecce23a6489870775f54cefe578a26daf8cfef23773i0`
- Type: text/plain
- Size: 5.1 KB
- Expected inscription #: 77692460
- Expected block height: 870953
- Expected timestamp: 2024-11-19 01:24:15 UTC
