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
| `data/week.json` | Current week’s 15 stories |
| `scripts/refresh.py` | Monday refresher |

## Schema

```json
{
  "weekOf": "2026-09-22",
  "updatedAt": "2026-09-26T09:00:00Z",
  "stories": [
    {
      "title": "…",
      "summary": "2–3 sentence card blurb",
      "summaryLong": "~500-word verified excerpt for in-page expand",
      "summaryLongNote": "optional honesty note if shorter",
      "source": "Outlet name",
      "url": "https://…",
      "impact": 5,
      "youtube": "https://www.youtube.com/watch?v=…",
      "images": ["https://…"]
    }
  ]
}
```

- `weekOf` — Monday of the prior calendar week  
- `impact` — 1–5 → visual tiers: hero / featured / standard / compact / minimal  
- `youtube` — optional; high-impact stories get a larger embed  
- Missing/broken images → calm gray placeholder (no invented credits)

## Monday refresh

```bash
python3 scripts/refresh.py
```

Cron example (Mondays 06:00) — refresh then push so Pages updates:

```cron
0 6 * * 1 cd /path/to/whats-good-in-the-world && python3 scripts/refresh.py && git add data/week.json && git commit -m "weekly refresh" && git push >> /tmp/whats-good-refresh.log 2>&1
```

**Assumptions:** searches favor **USA stories (majority)**, with **Oregon** when available (Portland, coast, Cascades, Willamette, OSU/UO, local nonprofits), plus accessible tech/space/open-source writeups, conservation, art, and a little global variety only as needed to fill 15. Skips known paywall hosts. Scores with positivity heuristics plus USA/Oregon boosts. **Failure:** if fewer than ~8 solid candidates, exits non-zero and leaves the previous `week.json` intact.

**Positivity criteria:** conservation & recovery, public-health milestones, useful tech/open-source tools, restoration, accessibility, free museum/art wins. Avoid culture-war / contested framing.

## Images & paywalls

Only freely readable article URLs. Prefer org CDNs and Wikimedia. Hotlink failures are expected sometimes — placeholders are intentional.

## Live site (iPhone Safari)

**https://evolknives.github.io/whats-good-in-the-world/**

Static files — no build step. GitHub Pages serves from `main` branch root `/`.

### Re-publish after content refresh

```bash
python3 scripts/refresh.py   # updates data/week.json
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
