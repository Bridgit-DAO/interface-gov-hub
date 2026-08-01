# Accessing Development Server

## Current Setup
- **Development URL**: `https://dev.hub.themetalayer.org` (nginx → port 8001)
- **Development Server**: Running on port 8001
- **Production Server**: Running on port 8000 (via nginx)

## Access Methods

### Method 1: Direct IP Access (Current)
```
http://216.238.91.120:8001
```
**Note**: This may be blocked by cloud provider firewall or may hang if there are slow operations.

### Method 2: SSH Tunnel (Recommended - Most Reliable)
From your local machine, create an SSH tunnel:

```bash
ssh -L 8001:localhost:8001 ubuntu@216.238.91.120
```

Then access: **http://localhost:8001** in your browser

**Advantages:**
- No firewall configuration needed
- Secure (encrypted tunnel)
- Always works
- Can keep tunnel open while developing

### Method 3: Canonical Dev URL (Best for Team Access)
```
https://dev.hub.themetalayer.org
```

Layer vanity: `https://[layer-slug].dev.hub.themetalayer.org`

Install/update nginx vhost: `sudo bash docs/install-hub-themetalayer-org.sh` (see `docs/GOVHUB_HUB_LAYER_VANITY.md`).

## Troubleshooting

If the page hangs:
1. Check browser console for JavaScript errors
2. Check which route is hanging (home page vs specific document page)
3. Try SSH tunnel method
4. Check server logs: `journalctl --user -u datatracker-dev.service -f`

## Quick Commands

```bash
# Check if dev server is running
systemctl --user status datatracker-dev.service

# View dev server logs
journalctl --user -u datatracker-dev.service -f

# Restart dev server
systemctl --user restart datatracker-dev.service
```
