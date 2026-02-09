# Hypothesis Integration - Quick Start Guide

## For End Users

### How to Enable Annotations

1. **Open any RFC or Internet-Draft** in HTML view
2. **Click the sidebar toggle** button (top right)
3. **Navigate to the "Prefs" tab** in the sidebar
4. **Under "Annotations"**, select **"Show annotations"**
5. **Page will reload** with annotations enabled

### How to Create an Annotation

**Anonymous (No Account Required):**
1. Select text in the document
2. Click the "Annotate" button that appears
3. Type your annotation
4. Click "Post to Public"

**With Hypothesis Account (Recommended):**
1. Sign up at https://hypothes.is/signup
2. Log in via the Hypothesis sidebar
3. Select text and annotate
4. Choose to make it public or private

### Tips for Using Annotations

- **Highlight only**: Click the highlighter icon to highlight without commenting
- **Page notes**: Click "Page Note" to comment on the entire document
- **Reply**: Click on any annotation to reply
- **Filter**: Use the sidebar to filter annotations by user or group
- **Share**: Copy the annotation link to share specific annotations

## For Developers

### Quick Test

```bash
# 1. Ensure Hypothesis is enabled
cd /home/ubuntu/datatracker
grep "HYPOTHESIS_ENABLED = True" ietf/settings.py

# 2. Start dev server
./dev-server.sh

# 3. Navigate to a document
# Open: http://localhost:8000/doc/html/rfc8989
# or: http://localhost:8000/doc/html/draft-ietf-example-00

# 4. Enable annotations via preferences
# Sidebar → Prefs → Annotations → Show annotations
```

### Verify Installation

Check these files were modified:
- ✅ `k8s/nginx-datatracker.conf` - CSP updated
- ✅ `k8s/nginx-auth.conf` - CSP updated
- ✅ `ietf/settings.py` - Hypothesis config added
- ✅ `ietf/templates/doc/document_html.html` - Client embedded
- ✅ `ietf/static/js/document_html.js` - Preference handling

### Configuration Options

```python
# Disable globally (in settings_local.py)
HYPOTHESIS_ENABLED = False

# Change default behavior
HYPOTHESIS_CONFIG['DEFAULT_VISIBILITY'] = 'always'  # Always show

# Customize branding
HYPOTHESIS_CONFIG['BRANDING']['ctaBackgroundColor'] = '#your-color'
```

## For Administrators

### Deployment Checklist

- [ ] Verify CSP changes in nginx configs
- [ ] Test in staging environment
- [ ] Monitor performance metrics
- [ ] Check browser console for errors
- [ ] Verify mobile responsiveness
- [ ] Test with different document types (RFC, Draft)
- [ ] Test with different revisions
- [ ] Collect initial user feedback

### Monitoring

Watch for:
- **CSP violations**: Check nginx logs
- **Performance**: Monitor page load times
- **Errors**: Check browser console and Django logs
- **Usage**: Track cookie preferences

### Rollback

If needed:
```python
# Quick disable via settings
HYPOTHESIS_ENABLED = False
```

Or revert nginx configs and redeploy.

## Common Issues

### "Annotations not loading"
- Check browser console for CSP errors
- Verify `HYPOTHESIS_ENABLED = True`
- Check `annotations` cookie value

### "Can't see my annotations"
- Annotations are revision-specific for drafts
- Check you're viewing the same revision
- Verify you're logged into Hypothesis

### "Performance is slow"
- Hypothesis client loads asynchronously
- Check network connection
- Try disabling highlights: `SHOW_HIGHLIGHTS = 'never'`

## Next Steps

### For Phase 2 Planning
- [ ] Set up Hypothesis API credentials
- [ ] Plan IETF account integration
- [ ] Design group annotation structure
- [ ] Plan moderation workflow

### Resources
- Full documentation: `HYPOTHESIS_INTEGRATION.md`
- Hypothesis docs: https://web.hypothes.is/help/
- Report issues: https://github.com/ietf-tools/datatracker/issues

---

**Questions?** Contact the IETF Tools Team
