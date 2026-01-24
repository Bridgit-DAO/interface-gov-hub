# Ordinals Integration - User Guide

## Overview

The **MLTF Datatracker** now supports submitting Internet-Drafts using **Bitcoin Ordinal inscriptions** as the source document. This guide will walk you through how to use this feature.

---

## What are Ordinals?

**Bitcoin Ordinals** are a way to inscribe data (images, text, documents, etc.) directly onto the Bitcoin blockchain. Each inscription has a unique ID and can be viewed on [ordinals.com](https://ordinals.com).

---

## Submitting a Draft from an Ordinal

### Step 1: Navigate to Submit Page

1. Log in to the MLTF Datatracker
2. Click **"Submit Draft"** in the navigation menu
3. You'll see two tabs: **"Upload File"** and **"From Ordinal"**

### Step 2: Switch to "From Ordinal" Tab

Click the **"From Ordinal"** tab to access the ordinal submission form.

### Step 3: Enter Inscription ID

1. In the **"Inscription ID"** field, enter the full inscription ID from ordinals.com
   - Example: `abc123def456ghi789jkl012mno345pqr678stu901vwx234yz`
2. The inscription ID should be alphanumeric and at least 10 characters long

### Step 4: Preview the Content

1. Click the **"Preview"** button next to the inscription ID field
2. Wait for the content to load (you'll see a spinning loader)
3. The preview will show:
   - **Content**: The actual inscription content (image, text, markdown, or HTML)
   - **Metadata**: Information about the inscription

#### Preview Examples

**For Images:**
- The image will be displayed directly in the preview area
- Maximum display height: 400px (maintains aspect ratio)

**For Text:**
- Plain text will be displayed in a scrollable text box
- Monospace font for readability

**For Markdown:**
- Markdown will be converted to HTML and displayed with formatting
- Supports headers, lists, code blocks, tables, etc.

**For HTML:**
- HTML will be displayed in a secure, sandboxed iframe
- The HTML cannot execute scripts or access your data

#### Metadata Displayed

- **Inscription ID**: The unique identifier
- **Inscription Number**: The sequential number (if available)
- **Block Height**: Bitcoin block where it was inscribed (if available)
- **Timestamp**: When it was inscribed (if available)
- **Content Type**: MIME type (e.g., `image/png`, `text/plain`)
- **Content Size**: Size in KB or MB

### Step 5: Fill in Draft Information

After previewing, fill in the required fields:

1. **Document Title** * (required)
   - Enter a clear, descriptive title for your draft

2. **Authors** * (required)
   - Enter comma-separated list of authors
   - Example: `John Doe, Jane Smith, Bob Johnson`

3. **Abstract** (optional)
   - Brief description of the document
   - Maximum ~500 characters recommended

4. **Working Group** (optional)
   - Select a working group from the dropdown
   - Leave blank if not associated with a group

### Step 6: Accept Terms

Check the box to agree to the MLTF submission terms.

### Step 7: Submit

Click the **"Submit Draft"** button to submit your draft.

**Note**: The submit button will be disabled until you successfully preview the ordinal.

---

## Viewing Your Ordinal Submission

### Submission Status Page

After submitting, you'll be redirected to the **Submission Status** page. Here you can see:

1. **Status Badge**: Current status (Submitted, Approved, Rejected, etc.)
2. **Source Badge**: Shows "🪙 Ordinal" in blue
3. **Submission Details**: Title, authors, submitted date, etc.
4. **Ordinal Metadata Card**: All inscription metadata
5. **"View on Ordinals.com" Link**: Verify the content on ordinals.com
6. **Content Preview**: The actual content rendered

### Submission List Page

From the **"My Submissions"** page, you can see all your submissions with:
- Status badge
- Source type badge (File or Ordinal)
- Quick access buttons

---

## Requirements & Limitations

### Supported Content Types

✅ **Supported:**
- Images: PNG, JPEG, GIF, SVG, WebP
- Text: Plain text (UTF-8)
- Markdown: GitHub-flavored markdown
- HTML: Standard HTML

❌ **Not Supported:**
- Video files
- Audio files
- Binary files (except images)
- Encrypted content
- Other file types

### Size Limit

- **Maximum Size**: 50 KB (51,200 bytes)
- Content larger than 50KB will be rejected during preview
- This is smaller than file upload limit (16MB) due to blockchain constraints

### Content Requirements

1. **Public Accessibility**: The inscription must be publicly viewable on ordinals.com
2. **Valid Format**: Content must be in a supported format
3. **No Malicious Content**: Content will be sanitized for security

---

## Troubleshooting

### "Invalid inscription ID format"

**Problem**: The inscription ID you entered doesn't match the expected format.

**Solution**:
- Check that you copied the full inscription ID from ordinals.com
- Ensure there are no spaces or special characters
- Inscription IDs are typically 64 characters long

### "Content too large: XX KB (max 50KB)"

**Problem**: The ordinal content exceeds the 50KB size limit.

**Solution**:
- Use a smaller image or compress it
- For text, consider splitting into multiple drafts
- For HTML, minify the content

### "Unsupported content type"

**Problem**: The content type is not supported.

**Solution**:
- Check the list of supported content types above
- Convert content to a supported format
- For documents, consider converting to markdown or plain text

### "Failed to load ordinal content"

**Problem**: The system couldn't fetch the content from ordinals.com.

**Solutions**:
1. **Check the inscription ID**: Make sure it's correct
2. **Try again**: ordinals.com might be temporarily unavailable
3. **Verify on ordinals.com**: Open the inscription in your browser first
4. **Wait and retry**: Network issues may be temporary

### "Preview button doesn't do anything"

**Problem**: Clicking the preview button has no effect.

**Solution**:
- Check your internet connection
- Try refreshing the page
- Check browser console for errors (F12)
- Try a different browser

### Preview shows "N/A" for metadata

**Problem**: Inscription number, block height, or timestamp shows "N/A".

**Explanation**: This is normal. The metadata API is not yet fully implemented. These fields will be populated in a future update.

**Impact**: This doesn't affect submission or content display.

---

## Tips & Best Practices

### Choosing Content for Ordinal Submissions

1. **Use appropriate formats**:
   - Images: Use PNG for graphics, JPEG for photos
   - Text: Use plain text or markdown for documents
   - HTML: Only for web-based content

2. **Optimize size**:
   - Compress images before inscribing
   - Minify HTML/CSS if needed
   - Keep under 50KB

3. **Test first**:
   - View your inscription on ordinals.com before submitting
   - Ensure it displays correctly

### Markdown Tips

When using markdown inscriptions:

1. **Headers**: Use `#`, `##`, `###` for structure
2. **Lists**: Use `-` or `1.` for lists
3. **Code**: Use triple backticks for code blocks
4. **Links**: Use `[text](url)` for links
5. **Tables**: Use pipes `|` for tables

Example:
```markdown
# Document Title

## Section 1

This is a paragraph with **bold** and *italic* text.

- List item 1
- List item 2

```code here```
```

### Security Considerations

1. **Verify content**: Always preview before submitting
2. **Check source**: Ensure the inscription is from a trusted source
3. **Report issues**: If you see malicious content, report it to admins

---

## FAQ

### Q: Can I edit an ordinal submission after submitting?

**A**: No, ordinal content is immutable (cannot be changed). If you need to make changes, you must:
1. Create a new inscription with the updated content
2. Submit a new draft with the new inscription ID

### Q: Can I submit multiple versions of a draft from ordinals?

**A**: Currently, only the initial submission can be from an ordinal. Future versions must be file uploads. This may be enhanced in the future.

### Q: What happens if the ordinal is deleted from ordinals.com?

**A**: If the inscription becomes unavailable, the content preview will fail to load. However, your submission metadata will remain in the system.

### Q: Can I mix file uploads and ordinals in the same draft?

**A**: Yes, you can submit the initial version from an ordinal and later versions as file uploads, or vice versa.

### Q: How do I find the inscription ID on ordinals.com?

**A**: 
1. Go to [ordinals.com](https://ordinals.com)
2. Search for or browse to your inscription
3. The inscription ID is shown in the URL: `https://ordinals.com/inscription/YOUR_ID_HERE`
4. Copy the entire ID (the long alphanumeric string)

### Q: Does submitting from an ordinal cost anything?

**A**: No, submitting a draft from an ordinal is free. However, creating the ordinal inscription on Bitcoin does have a cost (paid when you create the inscription, not when you submit).

### Q: What's the difference between file upload and ordinal submission?

| Feature | File Upload | Ordinal |
|---------|-------------|---------|
| **Max Size** | 16MB | 50KB |
| **Storage** | MLTF server | Bitcoin blockchain |
| **Permanence** | Server-dependent | Blockchain permanent |
| **Verification** | File hash | On-chain verification |
| **Cost** | Free | Bitcoin fees (one-time) |

---

## Examples

### Example 1: Submitting a Markdown Document

1. Go to ordinals.com and find your markdown inscription
2. Copy the inscription ID: `abc123...xyz`
3. Go to MLTF Submit page → "From Ordinal" tab
4. Paste inscription ID, click "Preview"
5. See your markdown rendered as HTML
6. Fill in title: "My Technical Specification"
7. Fill in authors: "John Doe"
8. Submit!

### Example 2: Submitting an Image-Based Draft

1. You have a diagram inscribed as an ordinal
2. Copy inscription ID from ordinals.com
3. Preview on MLTF submit page
4. Image displays in preview
5. Add title and metadata
6. Submit successfully

---

## Getting Help

If you encounter issues:

1. **Check this guide**: Review the troubleshooting section
2. **Contact admins**: Use the contact form or email
3. **Report bugs**: Submit an issue with details:
   - What you were trying to do
   - What went wrong
   - Inscription ID (if applicable)
   - Screenshots if helpful

---

## Updates & Changelog

### Version 1.0 (2026-01-23)
- Initial release
- Support for images, text, markdown, HTML
- Preview functionality
- Metadata display
- External verification links

### Planned Features
- Inscription number, block height, timestamp fetching
- Version support (new versions from ordinals)
- Bulk submissions
- Advanced filtering

---

**Last Updated**: 2026-01-23  
**Version**: 1.0  
**Status**: Production Ready (pending deployment)  

For questions or feedback, contact the MLTF administrators.
