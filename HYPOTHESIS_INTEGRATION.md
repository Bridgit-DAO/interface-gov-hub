# Hypothesis Annotation Integration

## Overview

This document describes the integration of Hypothesis web annotation capabilities into the IETF Datatracker's document viewing system. The integration enables collaborative annotation of RFCs and Internet-Drafts.

## Implementation Summary

**Integration Type:** Direct Client Embedding (Phase 1)  
**Status:** Active  
**Date Implemented:** January 26, 2026

## Features

### Phase 1 Features (Current)
- ✅ Anonymous public annotations
- ✅ Optional Hypothesis account integration
- ✅ User preference controls for enabling/disabling annotations
- ✅ Document revision-specific annotation spaces
- ✅ Responsive design compatible with mobile devices
- ✅ IETF-branded annotation interface

### Planned Features (Future Phases)
- 🔄 IETF account integration with automatic Hypothesis account creation
- 🔄 Private working group annotations
- 🔄 Role-based annotation permissions (WG chairs, ADs, etc.)
- 🔄 Integration with document review process
- 🔄 Moderation tools

## Architecture

### Components Modified

1. **Content Security Policy** (`k8s/nginx-*.conf`)
   - Added `https://hypothes.is` to allowed script sources
   - Added `connect-src` for Hypothesis API calls

2. **Django Settings** (`ietf/settings.py`)
   - Added `HYPOTHESIS_ENABLED` flag
   - Added `HYPOTHESIS_CONFIG` dictionary with branding and behavior settings

3. **Document Template** (`ietf/templates/doc/document_html.html`)
   - Added Hypothesis client script loader
   - Added configuration script with IETF branding
   - Added user preference controls in sidebar

4. **JavaScript** (`ietf/static/js/document_html.js`)
   - Added "annotations" preference handling
   - Integrated with existing preference system

## Configuration

### Settings

```python
# In ietf/settings.py
HYPOTHESIS_ENABLED = True  # Set to False to disable globally

HYPOTHESIS_CONFIG = {
    'EMBED_URL': 'https://hypothes.is/embed.js',
    'DEFAULT_VISIBILITY': 'user',  # off by default, user can enable
    'BRANDING': {
        'appBackgroundColor': '#f8f9fa',
        'ctaBackgroundColor': '#0d6efd',
        'ctaTextColor': '#ffffff',
        'selectionFontFamily': 'Inter, sans-serif',
    },
    'ENABLE_EXPERIMENTAL_NEW_NOTE_BUTTON': True,
    'SHOW_HIGHLIGHTS': 'whenSidebarOpen',
}
```

### Disabling Annotations

To disable annotations globally:
```python
HYPOTHESIS_ENABLED = False
```

To disable for specific environments, add to `settings_local.py`:
```python
HYPOTHESIS_ENABLED = False
```

## Document Revision Strategy

### RFCs (Immutable Documents)
- Each RFC has a single annotation space
- Tagged with: `rfc:<number>` and `ietf:rfc`
- Example: RFC 8989 → tags: `rfc:8989`, `ietf:rfc`

### Internet-Drafts (Versioned Documents)
- Each revision has its own annotation space
- Tagged with: `draft:<name>-<rev>` and `ietf:draft`
- Example: draft-ietf-example-00 → tags: `draft:draft-ietf-example-00`, `ietf:draft`

This approach ensures:
- Annotations remain relevant to specific document versions
- Historical annotations are preserved
- Users can compare annotations across revisions

## User Experience

### Enabling Annotations

Users can enable annotations in two ways:

1. **Via Preferences (Persistent)**
   - Click the sidebar toggle button
   - Navigate to "Prefs" tab
   - Under "Annotations", select "Show annotations"
   - Page reloads with annotations enabled

2. **Via Cookie (Manual)**
   - Set cookie: `annotations=on`
   - Refresh page

### Using Annotations

**Anonymous Users:**
- Can view all public annotations
- Can create public annotations (no account required)
- Annotations are attributed to "Anonymous"

**Hypothesis Account Users:**
- Can create private annotations
- Can join annotation groups
- Can reply to annotations
- Full annotation history and management
- Sign up at: https://hypothes.is/signup

### Annotation Interface

The Hypothesis sidebar provides:
- **Highlight tool**: Select text and click to annotate
- **Page notes**: Add notes about the entire document
- **Replies**: Respond to other annotations
- **Filtering**: View only your annotations or group annotations
- **Sorting**: Sort by location, time, or author

## Technical Details

### Content Security Policy

The CSP has been updated to allow:
- `script-src`: Loading Hypothesis client from `https://hypothes.is`
- `connect-src`: API calls to Hypothesis servers
- `default-src`: General resources from Hypothesis domain

### Performance Impact

- **Initial Load**: +~150KB (Hypothesis client, gzipped)
- **Runtime**: Minimal impact, client loads asynchronously
- **Caching**: Hypothesis client is cached by browser

### Browser Compatibility

Hypothesis supports:
- Chrome/Edge (latest 2 versions)
- Firefox (latest 2 versions)
- Safari (latest 2 versions)
- Mobile browsers (iOS Safari, Chrome Mobile)

## Privacy & Security

### Data Storage
- Annotations are stored on Hypothesis servers
- Subject to Hypothesis privacy policy: https://web.hypothes.is/privacy/
- IETF does not store annotation data

### Anonymous Annotations
- No personal data collected for anonymous annotations
- IP addresses may be logged by Hypothesis for abuse prevention

### User Accounts
- Users who create Hypothesis accounts are subject to Hypothesis terms
- IETF does not have access to Hypothesis user data

### Moderation
- Public annotations are subject to Hypothesis community guidelines
- Report inappropriate content via Hypothesis interface
- Future: IETF-specific moderation capabilities

## Troubleshooting

### Annotations Not Loading

1. **Check browser console** for CSP errors
2. **Verify settings**: Ensure `HYPOTHESIS_ENABLED = True`
3. **Check cookie**: Ensure `annotations` cookie is not set to `off`
4. **Clear cache**: Try hard refresh (Ctrl+Shift+R / Cmd+Shift+R)

### Annotations Not Visible

1. **Check filter settings** in Hypothesis sidebar
2. **Verify document revision**: Annotations are revision-specific
3. **Check tag filters**: Ensure correct tags are applied

### Performance Issues

1. **Disable highlights**: Set `SHOW_HIGHLIGHTS = 'never'` in config
2. **Reduce annotation load**: Use group filters
3. **Check network**: Hypothesis requires internet connection

## Development

### Local Testing

1. Ensure `HYPOTHESIS_ENABLED = True` in `settings_local.py`
2. Start development server: `./dev-server.sh`
3. Navigate to any document HTML view
4. Enable annotations via preferences

### Testing Different Scenarios

```python
# Test with annotations enabled by default
HYPOTHESIS_CONFIG['DEFAULT_VISIBILITY'] = 'always'

# Test with different branding
HYPOTHESIS_CONFIG['BRANDING']['ctaBackgroundColor'] = '#ff0000'

# Test with sidebar auto-open
# In template, change: openSidebar: true
```

## Deployment

### Production Deployment

1. **Verify CSP changes** are deployed to nginx
2. **Test in staging** environment first
3. **Monitor performance** after deployment
4. **Collect user feedback** via GitHub issues

### Rollback Procedure

If issues arise:
```python
# In settings_local.py
HYPOTHESIS_ENABLED = False
```

Or revert nginx CSP changes and redeploy.

## Future Enhancements

### Phase 2: IETF Account Integration
- Automatic Hypothesis account creation for IETF users
- Single sign-on experience
- Role-based permissions

### Phase 3: Advanced Features
- Private working group annotation spaces
- Integration with document review workflow
- Email notifications for new annotations
- Annotation export/import capabilities
- Moderation dashboard for chairs/ADs

### Phase 4: Analytics
- Track annotation engagement
- Popular documents for annotations
- User adoption metrics
- Community insights

## Support

### For Users
- Hypothesis Help: https://web.hypothes.is/help/
- IETF Datatracker Issues: https://github.com/ietf-tools/datatracker/issues

### For Developers
- Hypothesis Developer Docs: https://h.readthedocs.io/
- Hypothesis API: https://h.readthedocs.io/en/latest/api-reference/

## References

- Hypothesis Project: https://hypothes.is
- Hypothesis GitHub: https://github.com/hypothesis
- Via HTML Proxy: https://github.com/hypothesis/viahtml
- Hypothesis Client: https://github.com/hypothesis/client

## Changelog

### 2026-01-26 - Phase 1 Implementation
- Added direct client embedding
- Implemented user preferences
- Added document revision strategy
- Updated CSP for Hypothesis domain
- Created documentation

---

**Maintained by:** IETF Tools Team  
**Last Updated:** January 26, 2026
