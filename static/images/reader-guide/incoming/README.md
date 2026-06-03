# Reader guide GIFs (How to participate modal)

**Do not paste GIFs into Cursor chat** — attachments are saved as a single JPEG frame and will not animate.

## Deploy real `.gif` files

1. Copy your three screen recordings (exported as **GIF**, 800×500) here:

   - `comment.gif`
   - `propose.gif`
   - `invite.gif`

   Example from your laptop:

   ```bash
   scp comment.gif propose.gif invite.gif ubuntu@YOUR_SERVER:/home/ubuntu/gov-hub-prod/static/images/reader-guide/incoming/
   ```

2. On the server:

   ```bash
   cd /home/ubuntu/gov-hub-prod
   bash scripts/deploy_reader_guide_gifs.sh
   systemctl --user restart datatracker.service
   ```

The script checks `file` reports `GIF image`, copies with a content-hash filename, updates `manifest.json`, and bumps the build number for cache busting.
