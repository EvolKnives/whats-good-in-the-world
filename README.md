# What's Good In The World?

A phone-first single page with **15** uplifting stories drawn fresh from a larger pool each visit (pool rebuilt from the **prior calendar week** on Mondays). Sparse Apple-inspired layout: large type, soft rounded media, generous whitespace, subtle scroll fades. Story footprint scales with an `impact` score (1–5).

## Preview locally

```bash
cd /workspace/five-good-things
python3 -m http.server 8080
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/) (or your machine’s LAN IP on a phone). Prefer a local server over `file://` so `fetch("data/week.json")` works.

## Files

| Path | Role |
|------|------|
| `index.html` | Page shell — title **What's Good In The World?** |
| `styles.css` | Phone-first layout, tiers, soft motion |
| `app.js` | Loads JSON, sorts by impact, IntersectionObserver reveals |
| `data/week.json` | Featured 15 (`stories`) plus larger `pool` for Refresh |
| `scripts/refresh.py` | Monday refresher — expands pool + sets featured 15 |

## Schema

```json
{
  "weekOf": "2026-09-22",
  "updatedAt": "2026-09-26T09:00:00Z",
  "highlights": ["stable-slug-a", "stable-slug-b", "stable-slug-c"],
  "stories": [ { "id": "stable-slug", "title": "…", "impact": 5, "topics": ["Science"], "whyMatters": "…" } ],
  "pool": [ { "id": "stable-slug", "title": "…" } ]
}
```

Each story object:

- `id` — stable slug used by Refresh to avoid repeats  
- `title`, `summary` — card blurb (2–3 sentences)  
- `summaryLong` — verified in-page expand text (~don’t invent quotes/numbers)  
- `summaryLongNote` — optional honesty note if shorter  
- `source`, `url`, `impact` (1–5), optional `youtube`, `images[]`
- `whyMatters` — short grounded one-liner shown in the expand panel (“Why this is good”); never invent claims  
- `topics[]` — 1–3 tags from: Climate, Health, Oregon, Science, Tech, Art, Achievement, Community  
- `metrics[]` — optional `{label, value}` chips; **only** when the number is clearly in the summary/title/source  
- `readMinutes` — optional; otherwise the UI estimates from `summaryLong` (~200 wpm)  
- `actionUrl` + `actionLabel` — optional “Do one thing” CTA; only real free reputable links (volunteer, open tools, museum/open-access). Skip if unsure.

Also:

- `weekOf` — Monday of the prior calendar week (first-paint label)  
- `stories` — featured **15** for first load  
- `pool` — ~30–45 stories; **Refresh** picks 15 whose ids are disjoint from what’s on screen (session-aware rotation)  
- `highlights` — optional array of up to 3 story ids for the “This week in three wins” strip (else auto top-3 by impact)  
- `impact` — 1–5 → hero / featured / standard / compact / minimal  
- Missing/broken images → calm gray placeholder (no invented credits)

### UI extras

- **Topic chips** narrow the current fifteen (AND across selected topics); empty state if none match.  
- **Quiet-list** density toggle (Compact / Comfortable) persists in `localStorage` (`wgw-density`).  
- **Read-time** badge and **metric** chips on cards; **whyMatters** + optional micro-action inside expand.

## Monday refresh

```bash
python3 scripts/refresh.py
```

Cron example (Mondays 06:00) — refresh then push so Pages updates:

```cron
0 6 * * 1 cd /path/to/whats-good-in-the-world && python3 scripts/refresh.py && git add data/week.json && git commit -m "weekly refresh" && git push >> /tmp/whats-good-refresh.log 2>&1
```

**Assumptions:** searches favor **USA stories (majority)**, with **Oregon** when available (Portland, coast, Cascades, Willamette, OSU/UO, local nonprofits), plus accessible tech/space/open-source writeups, conservation, art, **recent human achievements**, and a little global variety only as needed. Builds a **pool of ~30–45**. Soft mix targets include tech, art, and ~3–5 achievement-flavored stories among a featured 15 (and a healthy share of the pool). Skips known paywall hosts. Scores with positivity / tech / art / achievement heuristics plus USA/Oregon boosts. **Failure:** if fewer than ~8 solid candidates, exits non-zero and leaves the previous `week.json` intact.

### Fresh set on every open

Each page load picks a **fresh 15** from `pool` (shuffled; prefers unique primary photos). The header “Week of …” label is pool provenance from the Monday harvest—not a fixed digest that stays until next Monday.

### In-page Refresh

The footer **Refresh** button does **not** wait on a network re-harvest. It instantly chooses 15 stories from `pool`, preferring ids not already seen this week, re-renders, scrolls to top, and toasts **“Fifteen new stories”**. `localStorage` remembers the full seen-id round across page opens; when the pool cannot fill another unseen set, it starts a new round with a **“You’ve seen the rest — starting a new round”** toast. A new `weekOf` soft-resets the round.

**Positivity criteria:** conservation & recovery, public-health milestones, useful tech/open-source tools, restoration, accessibility, free museum/art wins, and **human achievements** (personal/team records, maker builds, science/tech milestones, community goals met, wildlife release successes). Prefer USA + Oregon when available. Avoid culture-war / contested framing.

## Images & paywalls

Only freely readable article URLs. Prefer org CDNs and Wikimedia. Hotlink failures are expected sometimes — placeholders are intentional.

## Live site (iPhone Safari)

**https://evolknives.github.io/whats-good-in-the-world/**

Static files — no build step. GitHub Pages serves from `main` branch root `/`.

### Re-publish after content refresh

```bash
python3 scripts/refresh.py   # updates featured 15 + pool in data/week.json
git add data/week.json && git commit -m "weekly refresh" && git push
```

Monday deploy = refresh then `git push` (Pages updates in ~1 minute).

### Other hosts

- **Netlify Drop:** drag this folder onto [https://app.netlify.com/drop](https://app.netlify.com/drop).
- **Cloudflare Pages:** connect the repo; framework preset **None**; output directory `/`.

## In-page expand

Tap **Read more** on a card for a smooth in-page disclosure (`summaryLong`). **Read original** opens the free source. One panel open at a time.


## Share

- Header **Share** shares the week URL (`navigator.share` on iOS Safari; otherwise copies the link).
- Each story has a quiet **Share** control that deep-links with `#story-…`.
- Confirmation toast: **Shared** after native share, **Link copied** on clipboard fallback.
- No social icon rows — one sparse pill button only.
