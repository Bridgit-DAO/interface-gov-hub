# Teilhard Test campaign – staging files (gov-hub-dev)

Drop files here **before** they are registered as Gov Hub artifacts or campaign assets.

## Deck (required for `/docs/slides`)

Copy your PDF here as:

```text
The_Teilhard_Test_Synthesis.pdf   # slide deck (agent drop 9f36b53f)
The_Teilhard_Test.pdf             # primary paper PDF with images (agent drop 6ef4256e)
```

Latest copies synced from agent drop on 2026-08-19.

Example from your laptop:

```bash
scp "/Users/daveed/Downloads/The_Teilhard_Test_Synthesis.pdf" \
  ubuntu@YOUR_SERVER:/home/ubuntu/gov-hub-dev/static/campaign/teilhard/incoming/The_Teilhard_Test_Synthesis.pdf
```

After artifacts are enabled on **The Overweb** (`the-overweb`), implementation will:

1. Copy or link this file into the artifact/media store
2. Create an Overweb artifact (subtype `slide_deck`)
3. Wire `teilhardtest.com` (dev) route `/docs/slides` to that artifact

## Statement (campaign copy)

Markdown source (not a Gov Hub draft yet):

```text
../statement.md
```

Rendered at `/docs/statement` when the campaign module is implemented. Endorsements target this page.

## Already in Gov Hub (do not duplicate here)

| Asset | Location |
|-------|----------|
| Primary paper | Draft `8a37qe9r` – https://dev.govhub.live/doc/draft/8a37qe9r/ (or local :8001) |
| Ordinal | Same submission – inscription metadata on the draft |
| Substack | External URL only: https://gometa.substack.com/p/the-teilhard-test |

## Seed config

`../campaign-seed.json` – routes, refs, and CTAs for dev implementation.

## Dev URLs (live)

| Page | URL |
|------|-----|
| Home | http://127.0.0.1:8001/campaign/teilhard/ or https://dev.govhub.live/campaign/teilhard/ |
| Paper | `/campaign/teilhard/docs/paper/` |
| Statement | `/campaign/teilhard/docs/statement/` |
| Slides | `/campaign/teilhard/docs/slides/` |
| Moderate endorsements | `/campaign/teilhard/admin/endorsements/` (admin/editor) |

Custom host `teilhard.dev.govhub.live` rewrites to `/campaign/teilhard/…` when DNS points at dev (see nginx).

## Optional later

- `hero.jpg` / `hero.png` – campaign homepage visual
- `talk.mp4` – conference video (or URL in campaign config)
