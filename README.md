# What's Good In The World?

A phone-first single page with **15** uplifting stories from the **prior calendar week**. Sparse Apple-inspired layout: large type, soft rounded media, generous whitespace, subtle scroll fades. Story footprint scales with an `impact` score (1–5).

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
  "stories": [ { "id": "stable-slug", "title": "…", "impact": 5 } ],
  "pool": [ { "id": "stable-slug", "title": "…" } ]
}
```

Each story object:

- `id` — stable slug used by Refresh to avoid repeats  
- `title`, `summary` — card blurb (2–3 sentences)  
- `summaryLong` — verified in-page expand text (~don’t invent quotes/numbers)  
- `summaryLongNote` — optional honesty note if shorter  
- `source`, `url`, `impact` (1–5), optional `youtube`, `images[]`

Also:

- `weekOf` — Monday of the prior calendar week (first-paint label)  
- `stories` — featured **15** for first load  
- `pool` — ~30–45 stories; **Refresh** picks 15 whose ids are disjoint from what’s on screen (session-aware rotation)  
- `impact` — 1–5 → hero / featured / standard / compact / minimal  
- Missing/broken images → calm gray placeholder (no invented credits)

## Monday refresh

```bash
python3 scripts/refresh.py
```

Cron example (Mondays 06:00) — refresh then push so Pages updates:

```cron
0 6 * * 1 cd /path/to/whats-good-in-the-world && python3 scripts/refresh.py && git add data/week.json && git commit -m "weekly refresh" && git push >> /tmp/whats-good-refresh.log 2>&1
```

**Assumptions:** searches favor **USA stories (majority)**, with **Oregon** when available (Portland, coast, Cascades, Willamette, OSU/UO, local nonprofits), plus accessible tech/space/open-source writeups, conservation, art, and a little global variety only as needed. Builds a **pool of ~30–45**, then sets a featured 15. Skips known paywall hosts. Scores with positivity heuristics plus USA/Oregon boosts. **Failure:** if fewer than ~8 solid candidates, exits non-zero and leaves the previous `week.json` intact.

### In-page Refresh

The footer **Refresh** button does **not** wait on a network re-harvest. It instantly chooses 15 stories from `pool` with ids disjoint from the current set (falling back to maximize-new if the pool is tight), re-renders, scrolls to top, and toasts **“Fifteen new stories”**. `sessionStorage` remembers recent ids so repeated taps keep rotating.

**Positivity criteria:** conservation & recovery, public-health milestones, useful tech/open-source tools, restoration, accessibility, free museum/art wins. Avoid culture-war / contested framing.

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
- No social icon rows — one sparse pill button only.
