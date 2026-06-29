# Cursor Briefing: Signal Artifact Design

> **Architecture (consolidated):** see [`docs/signal_artifact_architecture.md`](docs/signal_artifact_architecture.md) — artifact type, publish SLA, lifecycle/shorties, engagement, phasing. This file remains the implementation briefing (schema, UI, LLM prompt, MVP).

## Purpose

Design and implement a reusable **Signal Artifact** for Gov Hub.

A Signal Artifact is a living, versioned stream of short civic reflections, coordination principles, governance observations, or cultural signals. It should support manually authored content, JSON-loaded content, and LLM-generated continuation based on an existing ordered history and a defined content pattern.

The goal is not to build a generic quote widget. The goal is to build a small but powerful cultural-memory primitive for the Meta-Layer Governance Hub.

Signals should feel calm, thoughtful, civic, and alive.

## Core Concept

A Signal Artifact contains:

1. **An initial ordered array of Signal items**
2. **A content pattern** describing the voice, structure, constraints, and thematic boundaries
3. **A frequency** determining how often new Signals are published or suggested
4. **A version history** for each Signal
5. **Engagement metadata** such as reactions, bookmarks, shares, follows, and references
6. **Generation controls** allowing either manual creation or LLM-assisted continuation

Signals should never repeat unless intentionally reissued as a new version or annotated historical reference.

## Mental Model

Think of this as:

- a daily civic reflection stream
- a lightweight governance artifact
- a cultural signal archive
- a living institutional memory object
- a bridge between homepage inspiration, governance philosophy, and participatory standards culture

A Signal may start as a sentence on the homepage, but over time it can become part of the platform's civic memory.

## Example Signal Tone

Signals should be short, clear, and meaningful without sounding corporate, sentimental, or hype-driven.

Examples:

- The systems shaping society are still editable.
- Every protocol shapes behavior.
- Coordination is infrastructure.
- Good governance is not control. It is the cultivation of trust across difference.
- The web connected information. The next layer may connect responsibility.
- Civilization is built from agreements maintained over time.
- Every interface teaches a philosophy.
- The future is not only built through invention, but through stewardship.
- We inherit systems. We also leave them behind for others.
- Thoughtful governance begins with thoughtful participation.

## Data Model

Use a flexible JSON-first model.

```ts
type SignalArtifact = {
  id: string;
  slug: string;
  title: string; // usually "Signals"
  description?: string;
  status: "draft" | "active" | "paused" | "archived";
  contentPattern: SignalContentPattern;
  frequency: SignalFrequency;
  generationMode: "manual" | "json" | "llm" | "hybrid";
  signals: SignalItem[];
  createdAt: string;
  updatedAt: string;
};

type SignalContentPattern = {
  name: string;
  voice: string;
  purpose: string;
  themes: string[];
  avoid: string[];
  length: {
    minWords?: number;
    maxWords?: number;
    maxLines?: number;
  };
  structure?: string;
  examples: string[];
};

type SignalFrequency = {
  cadence: "daily" | "weekly" | "manual" | "custom";
  timezone?: string;
  publishTime?: string; // HH:mm
  customCron?: string;
};

type SignalItem = {
  id: string;
  artifactId: string;
  sequenceNumber: number;
  canonicalText: string;
  status: "draft" | "scheduled" | "published" | "archived";
  source: "manual" | "json_import" | "llm_generated" | "edited_llm";
  versions: SignalVersion[];
  tags?: string[];
  referencedBy?: SignalReference[];
  reactions?: SignalReactions;
  createdAt: string;
  publishedAt?: string;
  updatedAt: string;
};

type SignalVersion = {
  versionNumber: number;
  text: string;
  authorType: "human" | "agent" | "system";
  authorId?: string;
  changeReason?: string;
  createdAt: string;
};

type SignalReference = {
  type: "draft" | "rfc" | "workgroup" | "guild" | "comment" | "external";
  id?: string;
  label?: string;
  url?: string;
};

type SignalReactions = {
  likes: number;
  bookmarks: number;
  shares: number;
  follows: number;
  comments?: number;
};
```

## Initial JSON Example

```json
{
  "id": "signals-govhub-primary",
  "slug": "signals",
  "title": "Signals",
  "description": "Short civic reflections for the Meta-Layer Governance Hub.",
  "status": "active",
  "generationMode": "hybrid",
  "frequency": {
    "cadence": "daily",
    "timezone": "America/Los_Angeles",
    "publishTime": "08:00"
  },
  "contentPattern": {
    "name": "Gov Hub Civic Signal",
    "voice": "Calm, precise, civic, reflective, future-facing, non-corporate.",
    "purpose": "Invite thoughtful participation in layered governance and shared stewardship without hype or emotional manipulation.",
    "themes": [
      "coordination",
      "stewardship",
      "collective intelligence",
      "living documents",
      "trust",
      "governance layers",
      "public-interest infrastructure",
      "cognitive freedom",
      "shared standards",
      "human agency"
    ],
    "avoid": [
      "startup hype",
      "crypto jargon",
      "aggressive activism",
      "fear-based messaging",
      "corporate inspiration",
      "generic motivational quotes",
      "utopian certainty"
    ],
    "length": {
      "minWords": 4,
      "maxWords": 24,
      "maxLines": 2
    },
    "structure": "Usually one sentence or two short lines. Aphoristic but grounded. No hashtags. No exclamation points unless explicitly approved.",
    "examples": [
      "The systems shaping society are still editable.",
      "Every protocol shapes behavior.",
      "Coordination is infrastructure.",
      "Good governance is not control. It is the cultivation of trust across difference.",
      "The web connected information. The next layer may connect responsibility."
    ]
  },
  "signals": [
    {
      "id": "sig-0001",
      "artifactId": "signals-govhub-primary",
      "sequenceNumber": 1,
      "canonicalText": "The systems shaping society are still editable.",
      "status": "published",
      "source": "manual",
      "versions": [
        {
          "versionNumber": 1,
          "text": "The systems shaping society are still editable.",
          "authorType": "human",
          "createdAt": "2026-05-26T08:00:00-07:00"
        }
      ],
      "tags": ["agency", "governance", "systems"],
      "reactions": {
        "likes": 0,
        "bookmarks": 0,
        "shares": 0,
        "follows": 0
      },
      "createdAt": "2026-05-26T08:00:00-07:00",
      "publishedAt": "2026-05-26T08:00:00-07:00",
      "updatedAt": "2026-05-26T08:00:00-07:00"
    }
  ]
}
```

## User Interface Requirements

### Homepage Signal Card

The homepage should show the current Signal in a quiet card, likely under or near quick stats.

Suggested display:

```txt
Signals
Signal #1842

Every protocol shapes behavior.

♡ 241    Bookmark    Share    Discuss
```

Keep the card calm. Do not make it look like social media bait.

### Logged-In Greeting

When logged in, the homepage can personalize the experience:

```txt
Welcome back, Daveed.
Today’s Signal:

The systems shaping society are still editable.
```

Personalization should feel warm but restrained.

### Signal Archive Page

Provide an archive where users can browse all published Signals in order.

Features:

- chronological feed
- filter by tag/theme
- search
- sort by most bookmarked / most shared / most referenced
- view version history
- see references to drafts, RFCs, workgroups, or guilds
- follow the artifact

### Admin / Steward Controls

Provide controls for:

- manually adding a Signal
- importing Signals from JSON
- editing a Signal, creating a new version
- scheduling Signals
- pausing frequency
- generating more Signals with LLM
- approving or rejecting generated Signals before publication
- marking a Signal as canonical, retired, or referenced

## LLM Generation Flow

The LLM should generate new Signals by receiving:

1. The full ordered list of previous Signals
2. The content pattern
3. The desired number of new Signals
4. Optional current cognitive environment/context
5. Explicit non-repetition instruction
6. Optional emphasis tags

The LLM should return structured JSON only.

### Prompt Template

```txt
You are generating new Signals for the Meta-Layer Governance Hub.

A Signal is a short civic reflection, coordination principle, or governance observation.

Do not repeat any previous Signal.
Do not paraphrase too closely.
Maintain continuity with the existing sequence.
Preserve the content pattern.
Avoid hype, slogans, corporate inspiration, fear, or generic motivational language.

CONTENT PATTERN:
{{contentPatternJson}}

PREVIOUS SIGNALS IN ORDER:
{{orderedSignalsJson}}

CURRENT COGNITIVE ENVIRONMENT:
{{context}}

Generate {{count}} new Signals.

Return JSON only in this shape:
{
  "signals": [
    {
      "text": "...",
      "tags": ["..."],
      "rationale": "Brief internal rationale for steward review."
    }
  ]
}
```

Generated Signals should default to `draft` status until approved by a human steward.

## Current Cognitive Environment

This should be an optional text field supplied manually or by an agent.

Examples:

```txt
People are increasingly concerned about AI influence, institutional distrust, fragmented discourse, and the need for transparent governance systems. Emphasize calm agency, civic trust, and the idea that shared systems can still be shaped intentionally.
```

or:

```txt
The community is discussing ML-Drafts, workgroup formation, and how to welcome newcomers without overwhelming them. Generate Signals about participation, standards, and shared stewardship.
```

## Versioning Rules

Every edit creates a new version.

Do not overwrite previous text silently.

A Signal item has one `canonicalText`, but older versions remain visible in version history.

Version history should include:

- previous text
- new text
- author type
- author identity if available
- timestamp
- change reason

## Engagement Rules

Signals can accumulate:

- likes
- bookmarks
- shares
- follows
- comments/discussions
- references from drafts, RFCs, workgroups, or guilds

Engagement should attach to the Signal item, not only to a version. However, version-level engagement may be added later if needed.

If a Signal changes substantially, preserve the version boundary clearly so users know which wording they originally reacted to or bookmarked.

## Important Product Principle

Signals should not become engagement bait.

The purpose is cultural continuity, civic memory, and reflective participation.

Design for:

- restraint
- dignity
- clarity
- traceability
- continuity
- human stewardship

Avoid:

- dopamine loops
- infinite-scroll addiction
- meme-like virality mechanics
- manipulative notification patterns

## Suggested MVP

Build these first:

1. JSON-backed Signal Artifact schema
2. Homepage Signal card
3. Manual Signal creation form
4. Signal archive page
5. Basic reactions: like, bookmark, share
6. Version history on edit
7. LLM generation endpoint returning draft Signals
8. Human approval before publish

Defer:

- complex reputation graph
- version-level reaction splits
- automatic context ingestion
- advanced recommendation algorithms
- cross-artifact citation graph visualization

## MVP Acceptance Criteria

- A Signal Artifact can be created from JSON.
- Signals render in chronological order.
- The homepage shows the current published Signal.
- A steward can manually add a Signal.
- A steward can edit a Signal and create a version record.
- A steward can request X new draft Signals from an LLM using all previous Signals plus the content pattern.
- Generated Signals are not auto-published.
- Users can like, bookmark, and share Signals.
- Users can view prior versions of a changed Signal.

## Design Feeling

The Signal Artifact should feel like a quiet observatory inside the governance platform.

Not a quote wall.
Not a social feed.
Not motivational wallpaper.

A living stream of civic intelligence.

A small daily proof that the culture is thinking.

