# Fashion Store Frontend Redesign Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Redesign Deal Finder into a vibrant, modern, high-energy fashion-store shopping experience with bold color, smooth animation, and stronger visual excitement while preserving the existing Flask API and deal-filtering behavior.

**Architecture:** Keep the current single-file Flask template (`templates/index.html`) and existing API endpoints (`/api/deals`, `/api/scrape`, `/api/status`, `/api/retailers`). Refactor the frontend in-place: add design tokens, a fashion-editorial hero, animated deal cards, stronger filter controls, and polished states without introducing a JS build step.

**Tech Stack:** Flask 3, server-rendered HTML template, vanilla CSS, vanilla JavaScript, existing `fetch()` API calls, optional Google Font CDN (`DM Sans` + `Playfair Display` or `Inter`) if acceptable for deployed Render app.

---

## Design Direction

Use a hybrid of:

- **Figma-style energy:** vibrant multi-color gradients, pill controls, clean typography, colorful hero moments.
- **Spotify-style app polish:** dark immersive background, elevated cards, motion, dense shopping grid.
- **Fashion-store atmosphere:** editorial hero copy, runway/sale language, bold tags, colorful promo-code cards, premium shopping CTA treatments.

Target visual language:

- Background: deep plum/near-black base with neon gradient orbs.
- Accent colors: hot pink, electric violet, citrus yellow, mint green, coral.
- Typography: bold display hero + clean readable card text.
- Motion: subtle float, shimmer, card lift, filter transition, copy-confirmation pulse.
- UX: keep existing filters/search/copy/refresh, but make them feel like a modern sale-shopping interface.

---

## Acceptance Criteria

- Existing API calls still work: `/api/deals`, `/api/scrape`, `/api/status`.
- Search, category filter, type filter, refresh scrape, polling, copy-code behavior all still work.
- The site has an obvious high-energy fashion-store feel above the fold.
- Deal cards look visually richer and remain readable on mobile.
- Deal cards display recognizable retailer/brand identity for major stores such as Amazon, Walmart, Target, Nike, H&M, Zara, ASOS, Best Buy, and other supported retailers.
- Google Analytics tracking is installed in a configurable way, with events for search, category/type filtering, deal clicks, coupon copies, refresh/scrape triggers, and popular-retailer engagement.
- Affiliate/deep links are supported so the site can grow into a monetized one-stop discount hub across all major retailers.
- Animations are smooth but respect `prefers-reduced-motion`.
- No new frontend build system is required.
- Deployment remains compatible with Render + Gunicorn.

---

### Task 1: Add visual design tokens and font imports

**Objective:** Establish the new high-energy fashion-store design language in CSS variables.

**Files:**
- Modify: `templates/index.html:7-31`

**Step 1: Update the `<head>` font setup**

Add this before `<style>`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800;900&family=Playfair+Display:wght@700;800&display=swap" rel="stylesheet">
```

**Step 2: Replace current `:root` tokens**

Replace the existing variables with:

```css
:root {
  --bg: #120814;
  --bg-2: #1a0d24;
  --surface: rgba(255,255,255,0.08);
  --surface-strong: rgba(255,255,255,0.13);
  --surface2: rgba(255,255,255,0.16);
  --border: rgba(255,255,255,0.18);
  --text: #fff8ff;
  --muted: rgba(255,248,255,0.68);
  --accent: #ff3fb4;
  --accent-2: #8b5cf6;
  --accent-3: #facc15;
  --accent-4: #2dd4bf;
  --accent-glow: rgba(255,63,180,0.24);
  --code-bg: rgba(18,8,20,0.78);
  --code-border: rgba(255,255,255,0.22);
  --success: #35f2a0;
  --danger: #fb7185;
  --radius: 24px;
  --radius-sm: 14px;
  --shadow: 0 24px 80px rgba(0,0,0,0.42);
  --shadow-card: 0 18px 44px rgba(0,0,0,0.28);
}
```

**Step 3: Update body styling**

Use:

```css
body {
  font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background:
    radial-gradient(circle at 10% 10%, rgba(255,63,180,0.28), transparent 32%),
    radial-gradient(circle at 90% 6%, rgba(139,92,246,0.28), transparent 34%),
    radial-gradient(circle at 50% 100%, rgba(45,212,191,0.18), transparent 36%),
    linear-gradient(135deg, var(--bg) 0%, var(--bg-2) 100%);
  color: var(--text);
  min-height: 100vh;
  overflow-x: hidden;
}
```

**Step 4: Verify**

Run:

```bash
python -m py_compile app.py
python app.py
```

Open `http://127.0.0.1:5050` and confirm the page loads with no console-breaking CSS syntax issues.

**Step 5: Commit**

```bash
git add templates/index.html
git commit -m "style: add fashion-store design tokens"
```

---

### Task 2: Build a fashion-editorial hero section

**Objective:** Replace the understated header with an energetic fashion sale hero.

**Files:**
- Modify: `templates/index.html:33-96`
- Modify: `templates/index.html:409-424`

**Step 1: Replace header markup**

Replace the current `<header>...</header>` with:

```html
<header class="hero-shell">
  <div class="hero-copy">
    <div class="eyebrow">LIVE DEAL DROP • COUPONS • FLASH SALES</div>
    <h1><span>Deal Finder</span> turns discounts into a shopping rush.</h1>
    <p>Discover fresh promo codes and limited-time deals across fashion, tech, big-box, and food brands — refreshed automatically so the best finds stay current.</p>
    <div class="hero-actions">
      <button id="refreshBtn" onclick="triggerScrape()">
        <svg id="refreshIcon" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" viewBox="0 0 24 24">
          <path d="M1 4v6h6M23 20v-6h-6"/>
          <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4-4.64 4.36A9 9 0 0 1 3.51 15"/>
        </svg>
        Refresh the Drop
      </button>
      <div class="last-updated" id="lastUpdated">—</div>
    </div>
  </div>
  <div class="hero-card" aria-hidden="true">
    <div class="hero-card-top">RUNWAY SAVINGS</div>
    <div class="hero-discount">70% OFF</div>
    <div class="hero-card-bottom">Promo codes, steals, flash deals</div>
  </div>
</header>
```

**Step 2: Add hero CSS**

Replace old header CSS with:

```css
.hero-shell {
  width: min(1180px, calc(100% - 40px));
  margin: 28px auto 0;
  min-height: 330px;
  padding: 36px;
  border: 1px solid rgba(255,255,255,0.16);
  border-radius: 34px;
  background:
    linear-gradient(135deg, rgba(255,63,180,0.26), rgba(139,92,246,0.22) 45%, rgba(45,212,191,0.16)),
    rgba(255,255,255,0.07);
  box-shadow: var(--shadow);
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) 360px;
  gap: 28px;
  align-items: center;
  position: relative;
  overflow: hidden;
}
.hero-shell::before {
  content: "";
  position: absolute;
  inset: -40%;
  background: conic-gradient(from 120deg, transparent, rgba(250,204,21,0.22), transparent, rgba(255,63,180,0.22), transparent);
  animation: auraSpin 18s linear infinite;
  opacity: 0.8;
}
.hero-copy, .hero-card { position: relative; z-index: 1; }
.eyebrow {
  display: inline-flex;
  padding: 8px 14px;
  border: 1px solid rgba(255,255,255,0.24);
  border-radius: 999px;
  color: #ffe4f4;
  background: rgba(255,255,255,0.10);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.14em;
}
.hero-copy h1 {
  max-width: 720px;
  margin-top: 20px;
  font-family: 'Playfair Display', serif;
  font-size: clamp(44px, 7vw, 86px);
  line-height: 0.92;
  letter-spacing: -0.055em;
}
.hero-copy h1 span {
  background: linear-gradient(90deg, #fff, #ffe066, #ff3fb4);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.hero-copy p {
  max-width: 660px;
  margin-top: 20px;
  color: var(--muted);
  font-size: 18px;
  line-height: 1.55;
}
.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
  margin-top: 26px;
}
.hero-card {
  min-height: 260px;
  padding: 26px;
  border-radius: 30px;
  background:
    linear-gradient(160deg, rgba(255,255,255,0.24), rgba(255,255,255,0.08)),
    linear-gradient(135deg, #ff3fb4, #8b5cf6 55%, #2dd4bf);
  box-shadow: 0 30px 80px rgba(0,0,0,0.34);
  transform: rotate(3deg);
  animation: floatCard 5s ease-in-out infinite;
}
.hero-card-top, .hero-card-bottom {
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.16em;
}
.hero-discount {
  margin: 38px 0;
  font-size: clamp(56px, 8vw, 92px);
  line-height: 0.86;
  font-weight: 900;
  letter-spacing: -0.08em;
}
@keyframes auraSpin { to { transform: rotate(360deg); } }
@keyframes floatCard { 50% { transform: rotate(-1deg) translateY(-10px); } }
```

**Step 3: Verify**

Open the homepage and confirm the hero is visible above the fold on desktop and does not hide the refresh button.

**Step 4: Commit**

```bash
git add templates/index.html
git commit -m "style: add fashion sale hero"
```

---

### Task 3: Restyle controls as shopping filters

**Objective:** Make search, category tabs, and type filters feel like high-energy shopping controls.

**Files:**
- Modify: `templates/index.html:97-181`
- Modify: `templates/index.html:426-447`

**Step 1: Update section labels and placeholders**

Change placeholder:

```html
<input type="text" id="searchInput" placeholder="Search brands, promo codes, sale drops…" oninput="renderDeals()">
```

Rename buttons:

```html
<button class="tab active" data-cat="all" onclick="setCategory(this)">✨ All Drops</button>
<button class="tab" data-cat="big-box" onclick="setCategory(this)">🛒 Big-box</button>
<button class="tab" data-cat="fashion" onclick="setCategory(this)">👗 Fashion</button>
<button class="tab" data-cat="tech" onclick="setCategory(this)">💻 Tech</button>
<button class="tab" data-cat="food" onclick="setCategory(this)">🍔 Food</button>
```

Type filter:

```html
<button class="type-btn active" data-type="all" onclick="setType(this)">All Finds</button>
<button class="type-btn" data-type="code" onclick="setType(this)">🎟 Codes</button>
<button class="type-btn" data-type="deal" onclick="setType(this)">🏷 Deals</button>
```

**Step 2: Restyle controls**

Update `.controls`, `#searchInput`, `.tab`, `.type-btn` to use pill glass styling:

```css
.controls {
  width: min(1180px, calc(100% - 40px));
  margin: 24px auto 0;
  padding: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
  border: 1px solid rgba(255,255,255,0.14);
  border-radius: 26px;
  background: rgba(255,255,255,0.07);
  backdrop-filter: blur(18px);
}
#searchInput {
  width: 100%;
  background: rgba(255,255,255,0.10);
  border: 1px solid rgba(255,255,255,0.18);
  color: var(--text);
  border-radius: 999px;
  padding: 13px 16px 13px 42px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.18s, box-shadow 0.18s, background 0.18s;
}
#searchInput:focus {
  border-color: rgba(255,63,180,0.8);
  box-shadow: 0 0 0 4px rgba(255,63,180,0.14);
  background: rgba(255,255,255,0.14);
}
.tab, .type-btn {
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.16);
  background: rgba(255,255,255,0.08);
  color: rgba(255,248,255,0.76);
  font-weight: 800;
  cursor: pointer;
  transition: transform 0.18s, background 0.18s, border-color 0.18s, color 0.18s;
}
.tab { padding: 10px 17px; font-size: 13px; }
.type-btn { padding: 9px 15px; font-size: 12.5px; }
.tab:hover, .type-btn:hover { transform: translateY(-2px); color: var(--text); }
.tab.active, .type-btn.active {
  color: #120814;
  border-color: transparent;
  background: linear-gradient(135deg, var(--accent-3), #ff8bd8);
  box-shadow: 0 12px 30px rgba(255,63,180,0.22);
}
```

**Step 3: Verify**

Click every category/type filter and confirm cards update exactly as before.

**Step 4: Commit**

```bash
git add templates/index.html
git commit -m "style: restyle shopping filters"
```

---

### Task 4: Upgrade deal cards into animated shopping cards

**Objective:** Make each deal feel like a shoppable fashion-store product tile.

**Files:**
- Modify: `templates/index.html:199-351`
- Modify: `templates/index.html:578-617`

**Step 1: Add card position metadata in `cardHTML(d)`**

Change the rendered card wrapper to include a category class:

```js
<div class="card card-${escAttr(d.category || 'general')}" style="--retailer-color:${color}">
```

**Step 2: Add a top ribbon inside the card**

In `cardHTML(d)`, after opening `.card`, add:

```html
<div class="card-ribbon">${d.type === "code" ? "CODE DROP" : "SALE FIND"}</div>
```

**Step 3: Restyle `.card`**

Use:

```css
.grid {
  width: min(1180px, calc(100% - 40px));
  margin: 22px auto 56px;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 18px;
}
.card {
  min-height: 245px;
  background:
    linear-gradient(145deg, rgba(255,255,255,0.15), rgba(255,255,255,0.06)),
    rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.16);
  border-radius: var(--radius);
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 13px;
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow-card);
  transition: transform 0.22s ease, border-color 0.22s ease, box-shadow 0.22s ease;
}
.card::before {
  content: "";
  position: absolute;
  inset: -40% -20% auto auto;
  width: 180px;
  height: 180px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--retailer-color, var(--accent)) 38%, transparent);
  filter: blur(10px);
  opacity: 0.62;
}
.card:hover {
  border-color: color-mix(in srgb, var(--retailer-color, var(--accent)) 70%, white 10%);
  transform: translateY(-7px) scale(1.012);
  box-shadow: 0 28px 70px rgba(0,0,0,0.40);
}
.card-ribbon {
  align-self: flex-start;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255,255,255,0.12);
  color: rgba(255,248,255,0.76);
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.16em;
}
.card-header, .card-title, .discount-tag, .code-box, .card-footer { position: relative; z-index: 1; }
```

**Step 4: Restyle card details**

Update these selectors:

```css
.retailer-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--retailer-color, #ff3fb4) 18%, rgba(255,255,255,0.08));
  border: 1px solid color-mix(in srgb, var(--retailer-color, #ff3fb4) 42%, rgba(255,255,255,0.14));
  font-size: 12px;
  font-weight: 900;
  color: #fff;
}
.card-title {
  font-size: 15.5px;
  line-height: 1.45;
  color: var(--text);
  font-weight: 800;
}
.discount-tag {
  width: fit-content;
  padding: 7px 11px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 900;
  color: #121014;
  background: linear-gradient(135deg, var(--success), #facc15);
}
.code-box {
  background: rgba(18,8,20,0.68);
  border: 1px dashed rgba(255,255,255,0.28);
  border-radius: 18px;
  overflow: hidden;
}
.copy-btn {
  background: linear-gradient(135deg, rgba(255,63,180,0.24), rgba(139,92,246,0.24));
  color: #fff;
}
```

**Step 5: Verify**

Confirm long deal text still wraps cleanly, code copy still works, and `View deal` links remain clickable.

**Step 6: Commit**

```bash
git add templates/index.html
git commit -m "style: upgrade animated deal cards"
```

---

### Task 5: Improve loading, toast, and copied states

**Objective:** Make refresh/copy feedback feel polished and energetic.

**Files:**
- Modify: `templates/index.html:364-393`
- Modify: `templates/index.html:483-522`
- Modify: `templates/index.html:621-646`

**Step 1: Restyle loading bar**

```css
#loadingBar {
  display: none;
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 5px;
  background: linear-gradient(90deg, #ff3fb4, #facc15, #2dd4bf, #8b5cf6, #ff3fb4);
  background-size: 240% 100%;
  animation: slide 1s linear infinite;
  z-index: 9999;
  box-shadow: 0 0 24px rgba(255,63,180,0.55);
}
```

**Step 2: Restyle toast**

```css
#toast {
  display: none;
  position: fixed;
  bottom: 24px;
  right: 24px;
  background: rgba(18,8,20,0.86);
  border: 1px solid rgba(255,255,255,0.18);
  border-radius: 18px;
  padding: 14px 18px;
  font-size: 13.5px;
  font-weight: 800;
  color: var(--text);
  z-index: 9999;
  animation: fadeIn 0.22s ease;
  max-width: 320px;
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(16px);
}
```

**Step 3: Update copy success text**

In `copyCode`, change `Copied!` to:

```js
Copied ✨
```

**Step 4: Verify**

Click refresh and copy a code. Confirm the feedback looks polished and no JavaScript errors appear.

**Step 5: Commit**

```bash
git add templates/index.html
git commit -m "style: polish interaction feedback"
```

---

### Task 6: Add reduced-motion and mobile polish

**Objective:** Keep the design accessible and responsive.

**Files:**
- Modify: `templates/index.html:395-401`

**Step 1: Replace current mobile CSS**

Use:

```css
@media (max-width: 860px) {
  .hero-shell {
    grid-template-columns: 1fr;
    padding: 26px;
  }
  .hero-card {
    min-height: 190px;
    transform: none;
  }
  .hero-actions { align-items: flex-start; }
}

@media (max-width: 640px) {
  .hero-shell, .controls, .stats-bar, .grid { width: min(100% - 28px, 1180px); }
  .hero-shell { margin-top: 14px; padding: 22px; border-radius: 26px; }
  .hero-copy p { font-size: 15.5px; }
  .controls { padding: 12px; border-radius: 22px; }
  .search-wrap { min-width: 100%; max-width: none; }
  .tabs, .type-filter { width: 100%; overflow-x: auto; flex-wrap: nowrap; padding-bottom: 2px; }
  .grid { grid-template-columns: 1fr; }
  #toast { left: 14px; right: 14px; bottom: 14px; max-width: none; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}
```

**Step 2: Verify mobile**

Use browser responsive mode or narrow the browser and check:

- Hero stacks properly.
- Tabs can scroll horizontally if crowded.
- Cards are one column.
- Toast does not overflow.

**Step 3: Commit**

```bash
git add templates/index.html
git commit -m "style: add responsive fashion layout"
```

---

### Task 7: Add a lightweight smoke test for frontend endpoints

**Objective:** Verify the redesign did not break the Flask routes or HTML contract.

**Files:**
- Create: `tests/test_app_smoke.py`
- Modify: `requirements.txt`

**Step 1: Add pytest dependency**

Append to `requirements.txt`:

```txt
pytest>=8.0.0
```

**Step 2: Create smoke tests**

Create `tests/test_app_smoke.py`:

```python
from app import app


def test_homepage_renders_deal_finder():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Deal Finder" in html
    assert "Refresh the Drop" in html
    assert "dealsGrid" in html


def test_api_deals_returns_json_shape():
    client = app.test_client()
    response = client.get("/api/deals")
    assert response.status_code == 200
    data = response.get_json()
    assert "deals" in data
    assert "count" in data
    assert isinstance(data["deals"], list)


def test_api_retailers_contains_fashion_category():
    client = app.test_client()
    response = client.get("/api/retailers")
    assert response.status_code == 200
    retailers = response.get_json()
    assert any(r["category"] == "fashion" for r in retailers)
```

**Step 3: Run tests**

```bash
python -m pytest tests/test_app_smoke.py -v
```

Expected: `3 passed`.

**Step 4: Commit**

```bash
git add requirements.txt tests/test_app_smoke.py
git commit -m "test: add frontend smoke tests"
```

---

### Task 8: Final verification against deployed behavior

**Objective:** Confirm the finished redesign works locally and remains deployment-safe.

**Files:**
- No code changes unless bugs are found.

**Step 1: Run syntax and tests**

```bash
python -m py_compile app.py
python -m pytest -v
```

**Step 2: Run locally**

```bash
python app.py
```

Open `http://127.0.0.1:5050`.

**Step 3: Manual UI checklist**

Verify:

- Homepage loads.
- Hero appears vibrant and fashion-store-like.
- Search filters deals.
- Category tabs filter deals.
- Type buttons filter deals.
- Copy button copies coupon code.
- Refresh button starts scrape and shows loading/toast.
- Cards look good on mobile width.

**Step 4: Deployment check**

If using Render auto-deploy from GitHub:

```bash
git status --short
git log --oneline -8
```

Push when ready:

```bash
git push origin main
```

Then verify deployed URL:

```bash
curl -sS https://discount-scraper.onrender.com/api/status
curl -sS https://discount-scraper.onrender.com/api/deals | python -m json.tool | head -40
```

**Step 5: Commit if final tweaks were needed**

```bash
git add templates/index.html tests/test_app_smoke.py requirements.txt
git commit -m "fix: polish fashion redesign"
```

---

## Phase 2: Brand Logos, Analytics, and Affiliate Discount Hub

These are part of the broader product direction, not throwaway nice-to-haves. Implement after the first visual refresh is stable so the site can become a recognizable, monetized, one-stop discount hub.

### Task 9: Add recognizable retailer and brand logos

**Objective:** Help users identify deals instantly by showing clear brand/retailer identity on every deal card.

**Files:**
- Modify: `templates/index.html`
- Modify: `app.py` if retailer metadata is currently too thin
- Optional create: `static/brand-logos/` for local logo assets if SVG/CDN/logo API is not preferred

**Step 1: Add a `brandLogos` map in frontend JavaScript**

Start with a lightweight in-template map so this does not require a database migration:

```js
const brandLogos = {
  amazon: { label: 'Amazon', type: 'text', mark: 'a' },
  walmart: { label: 'Walmart', type: 'text', mark: 'W★' },
  target: { label: 'Target', type: 'text', mark: '◎' },
  nike: { label: 'Nike', type: 'text', mark: 'NIKE' },
  hm: { label: 'H&M', type: 'text', mark: 'H&M' },
  zara: { label: 'Zara', type: 'text', mark: 'ZARA' },
  asos: { label: 'ASOS', type: 'text', mark: 'ASOS' },
  bestbuy: { label: 'Best Buy', type: 'text', mark: 'BBY' }
};
```

Use text marks first to avoid trademark asset licensing risk. If using official logos later, store source/licensing notes in `docs/brand-assets.md`.

**Step 2: Add a normalizer**

```js
function retailerKey(name = '') {
  return name.toLowerCase().replace(/&/g, 'and').replace(/[^a-z0-9]+/g, '');
}

function brandIdentity(name = '') {
  const key = retailerKey(name);
  return brandLogos[key] || { label: name || 'Retailer', type: 'text', mark: (name || '?').slice(0, 2).toUpperCase() };
}
```

**Step 3: Render brand identity in `cardHTML(d)`**

Replace the current emoji-only retailer badge with a brand mark plus name:

```html
<span class="brand-mark" aria-hidden="true">${esc(brand.mark)}</span>
<span>${esc(brand.label)}</span>
```

**Step 4: Style the marks**

```css
.brand-mark {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: rgba(255,255,255,0.92);
  color: #120814;
  font-size: 10px;
  font-weight: 950;
  letter-spacing: -0.04em;
  box-shadow: 0 8px 20px rgba(0,0,0,0.22);
}
```

**Step 5: Verify**

Confirm Amazon, Walmart, Target, Nike, H&M, Zara, ASOS, and Best Buy all display recognizable marks, and unknown retailers fall back to clean initials.

**Step 6: Commit**

```bash
git add templates/index.html app.py static/brand-logos docs/brand-assets.md
git commit -m "feat: add retailer brand identity to deal cards"
```

---

### Task 10: Add Google Analytics tracking

**Objective:** Track traffic, user behavior, popular categories, deal engagement, coupon-copy intent, and affiliate/conversion-adjacent metrics.

**Files:**
- Modify: `app.py`
- Modify: `templates/index.html`
- Optional modify: `.env.example` or README deployment notes

**Step 1: Add configurable measurement ID**

In `app.py`, expose the ID from environment:

```python
import os

@app.context_processor
def inject_analytics_config():
    return {
        'ga_measurement_id': os.getenv('GA_MEASUREMENT_ID', '')
    }
```

**Step 2: Add GA script only when configured**

In `templates/index.html` `<head>`:

```html
{% if ga_measurement_id %}
<script async src="https://www.googletagmanager.com/gtag/js?id={{ ga_measurement_id }}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', '{{ ga_measurement_id }}');
</script>
{% endif %}
```

**Step 3: Add a safe tracking helper**

```js
function trackEvent(name, params = {}) {
  if (typeof gtag !== 'function') return;
  gtag('event', name, params);
}
```

**Step 4: Track key interactions**

Add events:

```js
trackEvent('deal_search', { search_term: query });
trackEvent('category_filter', { category: currentCategory });
trackEvent('type_filter', { deal_type: currentType });
trackEvent('coupon_copy', { retailer: d.retailer, category: d.category });
trackEvent('deal_click', { retailer: d.retailer, category: d.category, deal_type: d.type });
trackEvent('refresh_scrape', { source: 'hero_button' });
```

Debounce search tracking so it does not fire on every keystroke.

**Step 5: Configure Render**

Set environment variable:

```bash
GA_MEASUREMENT_ID=G-XXXXXXXXXX
```

**Step 6: Verify**

- Local with no env var: page renders without GA script and no console errors.
- Local with env var: GA script appears in page source.
- In GA DebugView/Realtime: page view and interaction events appear.

**Step 7: Commit**

```bash
git add app.py templates/index.html README.md .env.example
git commit -m "feat: add configurable Google Analytics tracking"
```

---

### Task 11: Add affiliate-link support

**Objective:** Make outbound deal clicks monetizable without hard-coding affiliate details throughout the frontend.

**Files:**
- Modify: `app.py`
- Modify: `templates/index.html`
- Optional create: `affiliate_config.py` or `data/affiliate_retailers.json`
- Optional modify: README deployment notes

**Step 1: Define affiliate metadata**

Start with a JSON/config map keyed by normalized retailer:

```json
{
  "amazon": { "program": "amazon_associates", "tag_param": "tag", "tag_env": "AMAZON_ASSOCIATES_TAG" },
  "walmart": { "program": "walmart_affiliate", "tag_param": "affp1", "tag_env": "WALMART_AFFILIATE_ID" },
  "target": { "program": "target_affiliate", "tag_param": "afid", "tag_env": "TARGET_AFFILIATE_ID" }
}
```

Do not invent real affiliate IDs. Read IDs from environment variables only.

**Step 2: Add a backend link builder**

Create a function that appends affiliate params only for supported retailers and only when env vars exist. Preserve original URLs if no affiliate config is available.

**Step 3: Include both original and monetized URLs in deal JSON**

Return:

```json
{
  "url": "https://retailer.example/deal",
  "affiliate_url": "https://retailer.example/deal?tag=...",
  "affiliate_supported": true
}
```

**Step 4: Update frontend `View deal` links**

Use `affiliate_url || url`, open in a new tab, and track click events:

```html
<a href="${escAttr(d.affiliate_url || d.url)}" target="_blank" rel="nofollow sponsored noopener" onclick="trackDealClick('${escAttr(d.retailer)}', '${escAttr(d.category)}', '${escAttr(d.type)}')">View deal</a>
```

**Step 5: Verify**

- Without affiliate env vars, outbound links remain unchanged.
- With test env vars, supported retailers get tagged links.
- Links include `rel="nofollow sponsored noopener"`.
- GA event `deal_click` fires when configured.

**Step 6: Commit**

```bash
git add app.py templates/index.html data/affiliate_retailers.json README.md
git commit -m "feat: add affiliate link support"
```

---

### Task 12: Expand retailer coverage into a comprehensive discount hub

**Objective:** Scale from a small set of deal sources to broad coverage across all major retailer categories while keeping scraping/link handling maintainable.

**Files:**
- Modify: `app.py` or current scraper module(s)
- Optional create: `data/retailers.json`
- Optional create: `data/categories.json`
- Optional create: `docs/retailer-expansion.md`

**Step 1: Move retailer definitions into data**

Create a structured retailer registry:

```json
{
  "amazon": { "name": "Amazon", "category": "big-box", "homepage": "https://www.amazon.com", "affiliate_supported": true },
  "walmart": { "name": "Walmart", "category": "big-box", "homepage": "https://www.walmart.com", "affiliate_supported": true },
  "target": { "name": "Target", "category": "big-box", "homepage": "https://www.target.com", "affiliate_supported": true },
  "nike": { "name": "Nike", "category": "fashion", "homepage": "https://www.nike.com", "affiliate_supported": true },
  "hm": { "name": "H&M", "category": "fashion", "homepage": "https://www2.hm.com", "affiliate_supported": true },
  "zara": { "name": "Zara", "category": "fashion", "homepage": "https://www.zara.com", "affiliate_supported": false },
  "asos": { "name": "ASOS", "category": "fashion", "homepage": "https://www.asos.com", "affiliate_supported": true },
  "bestbuy": { "name": "Best Buy", "category": "tech", "homepage": "https://www.bestbuy.com", "affiliate_supported": true }
}
```

**Step 2: Add categories for expansion**

Initial categories:

- Big-box: Amazon, Walmart, Target, Costco, Sam's Club, Kohl's, Macy's
- Fashion: Nike, Adidas, H&M, Zara, ASOS, Nordstrom, Gap, Old Navy, Shein, Uniqlo
- Tech: Best Buy, Apple, Samsung, Dell, HP, Lenovo, Newegg, B&H Photo
- Beauty: Sephora, Ulta, Glossier, Fenty Beauty
- Home: Wayfair, IKEA, Home Depot, Lowe's, Overstock
- Travel: Expedia, Booking, Hotels.com, Priceline
- Food: DoorDash, Uber Eats, Grubhub, Starbucks, Domino's

**Step 3: Prefer official APIs/feeds where available**

For monetization and reliability, prioritize:

1. Affiliate network product/deal feeds.
2. Retailer official deal/coupon pages.
3. RSS/sitemap/public pages with stable markup.
4. Scraping only where allowed and technically stable.

**Step 4: Add expansion docs**

Document per retailer:

- source URL/API/feed
- category
- affiliate network/program
- allowed usage notes
- scraper/parser status
- last verified date

**Step 5: Add UI hooks for larger catalog**

Once retailer count grows, add:

- retailer search/autocomplete
- category landing sections
- “Popular Retailers” strip with logos
- “Trending Deals” or “Top Coupon Codes” section
- sort by newest, largest discount, codes first, retailer

**Step 6: Verify**

- `/api/retailers` returns all configured retailers.
- `/api/deals` stays fast enough for homepage load.
- Unknown/unsupported retailers still render safely.
- Affiliate links are only applied where configured.

**Step 7: Commit**

```bash
git add app.py data/retailers.json data/categories.json docs/retailer-expansion.md templates/index.html
git commit -m "feat: expand retailer registry for discount hub"
```

---

## Future Enhancements After Phase 2

1. Add sort controls: newest, largest discount, codes first, fashion first.
2. Add featured “Deal of the Moment” carousel using top coupon-code deals.
3. Add saved/favorite deals using localStorage.
4. Add `/api/metrics` for scrape count, source count, last successful refresh, and category totals.
5. Split CSS/JS into static files once the single template becomes hard to maintain.
6. Add newsletter/email capture for weekly discount roundups.
7. Add SEO landing pages by retailer and category once the retailer registry is stable.

---

## Implementation Notes

- Keep all existing JavaScript function names unless deliberately refactoring: `loadDeals`, `triggerScrape`, `startPolling`, `resetBtn`, `setCategory`, `setType`, `renderDeals`, `cardHTML`, `copyCode`, `showToast`.
- Avoid changing backend scraping logic during the design pass.
- Be careful with `color-mix()` support. The existing site already uses `color-mix()`, so keeping it is acceptable unless browser support requirements change.
- Do not introduce React/Vite/Tailwind for this pass; the repo is intentionally lightweight.
