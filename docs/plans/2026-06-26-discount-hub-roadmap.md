# Discount Hub Implementation Roadmap

> **For Hermes:** Use `subagent-driven-development` or the existing phase plan in `docs/plans/2026-06-26-fashion-store-redesign.md` to implement this roadmap task-by-task.

**Goal:** Turn Deal Finder into a credible, measurable, monetizable one-stop discount hub without scaling a fragile architecture.

**Core principle:** Do not expand to all major retailers until the existing app is stable, testable, visually credible, analytics-enabled, and affiliate-link-ready.

**Current architecture:** Flask backend in `app.py`, single frontend template in `templates/index.html`, cached deals in `deals.json`, deployed refresh via the `discount-website-refresh` cronjob hitting `/api/scrape` and polling `/api/status`.

---

## Locked Implementation Order

1. **Phase 0 — Stabilize foundation**
2. **Phase 1 — Redesign + brand marks**
3. **Phase 2 — Google Analytics**
4. **Phase 3 — Affiliate links**
5. **Phase 4 — Retailer registry**
6. **Phase 5 — Retailer expansion**
7. **Phase 6 — Cron/backend reliability**

---

## Phase 0 — Stabilize Foundation

**Objective:** Make the current app safe to change before product/design/monetization work.

**Recommended tasks:**

- Add pytest smoke tests for:
  - `/`
  - `/api/deals`
  - `/api/status`
  - `/api/retailers`
  - `/api/scrape`
- Add helpers in `app.py` for consistent deal objects:
  - `normalize_retailer_key(name)`
  - `build_deal(...)`
  - `decorate_deal(deal)`
  - `validate_deal(deal)`
- Refactor scrapers to use the helper instead of hand-building dictionaries in every source.
- Keep current external behavior unchanged.

**Technical requirements:**

- `pytest>=8.0.0`
- `tests/test_app_smoke.py`
- Backend deal normalization helpers

**Backend changes needed:** Yes — normalize the deal shape and reduce duplicate dictionary construction.

**Cron changes needed:** No immediate change.

**Done when:** Tests pass and current homepage/API behavior is unchanged.

---

## Phase 1 — Redesign + Brand Marks

**Objective:** Make Deal Finder feel like a credible modern discount/shopping destination.

**Recommended tasks:**

- Implement high-energy fashion-store visual redesign.
- Upgrade hero, filters, cards, loading/toast/copy states, and mobile layout.
- Add brand/retailer marks for Amazon, Walmart, Target, Nike, H&M, Zara, ASOS, Best Buy, etc.
- Prefer safe text/monogram marks first instead of downloaded official logo assets.
- Add fallback initials for unknown retailers.

**Technical requirements:**

- `templates/index.html` updates
- CSS for `.brand-mark`, upgraded `.retailer-badge`, and card layout
- Optional backend fields later:
  - `retailer_key`
  - `brand_mark`
  - `brand_color`

**Backend changes needed:** Light/optional in this phase. Can start frontend-only, but backend-provided brand metadata is better long term.

**Cron changes needed:** No.

**Done when:** Site is visually upgraded, cards identify brands quickly, and all existing filters/copy/refresh behavior still works.

---

## Phase 2 — Google Analytics

**Objective:** Measure user behavior before optimizing monetization.

**Recommended events:**

- Page view
- Search
- Category filter
- Type filter
- Retailer engagement
- Deal click
- Coupon copy
- Refresh/scrape click

**Technical requirements:**

- Render env var:

```bash
GA_MEASUREMENT_ID=G-XXXXXXXXXX
```

- Flask context processor in `app.py`:

```python
@app.context_processor
def inject_analytics_config():
    return {"ga_measurement_id": os.getenv("GA_MEASUREMENT_ID", "")}
```

- Conditional GA script in `templates/index.html`
- Safe JS helper:

```js
function trackEvent(name, params = {}) {
  if (typeof gtag !== "function") return;
  gtag("event", name, params);
}
```

- Debounced search tracking to avoid firing on every keystroke.

**Backend changes needed:** Yes — small config injection.

**Cron changes needed:** No.

**Done when:** Site works with or without `GA_MEASUREMENT_ID`, no console errors, and GA Realtime/DebugView shows events.

---

## Phase 3 — Affiliate Links

**Objective:** Make outbound clicks monetizable without hard-coding affiliate logic throughout the app.

**Recommended tasks:**

- Add `data/affiliate_retailers.json`.
- Add backend affiliate URL builder using environment variables only.
- Add `affiliate_url` and `affiliate_supported` to deal JSON.
- Update frontend to use `affiliate_url || url`.
- Add `rel="nofollow sponsored noopener"` to outbound deal links.
- Track `deal_click` events through GA when configured.

**Technical requirements:**

- `urllib.parse` for safe query handling
- Environment variables for real affiliate IDs
- Tests for:
  - no env var = original URL unchanged
  - env var present = tagged URL
  - existing query params preserved
  - unknown retailer = unchanged

**Backend changes needed:** Yes — affiliate decoration should live in backend deal normalization.

**Cron changes needed:** Not immediately, but future health checks should report affiliate coverage.

**Done when:** Existing links remain safe by default, supported retailers get affiliate URLs when configured, and link markup is compliant.

---

## Phase 4 — Retailer Registry

**Objective:** Move retailer/category/source metadata out of `app.py` so expansion becomes data-driven.

**Recommended tasks:**

- Create `data/retailers.json`.
- Create `data/categories.json`.
- Generate `RETAILERS`, keyword map, category filters, and `/api/retailers` from data.
- Add `/api/categories`.
- Add registry validation tests.

**Recommended retailer shape:**

```json
{
  "key": "amazon",
  "name": "Amazon",
  "domain": "amazon.com",
  "slug": "amazon",
  "category": "big-box",
  "color": "#FF9900",
  "brand_mark": "a",
  "homepage": "https://www.amazon.com",
  "affiliate_supported": true,
  "keywords": ["amazon", "prime day"]
}
```

**Backend changes needed:** Yes — this is the main architecture refactor before scaling.

**Cron changes needed:** Not immediately, but this prepares cron to reason about retailer counts/failures.

**Done when:** Adding a retailer mostly means editing data files, not code.

---

## Phase 5 — Retailer Expansion

**Objective:** Grow coverage in controlled batches instead of adding every retailer at once.

**Recommended expansion strategy:**

### Batch 1 — High-value obvious retailers

- Amazon
- Walmart
- Target
- Best Buy
- Nike
- Adidas
- H&M
- Zara
- ASOS
- Nordstrom
- Sephora
- Ulta
- Home Depot
- Lowe’s
- Wayfair
- Dell
- HP
- Lenovo

### Batch 2 — Monetization-focused

Prioritize retailers with:

- affiliate programs
- product/deal feeds
- public coupon pages
- stable URLs
- high consumer demand

### Batch 3 — Category depth

Add travel, food delivery, beauty, home goods, electronics, apparel, and marketplaces.

**Technical requirements:**

- retailer registry from Phase 4
- source priority system
- per-source scrape limits
- timeout protection
- per-retailer failure tracking
- dedupe improvements
- docs for source/API/feed status

**Backend changes needed:** Yes — eventually move from hard-coded retailer loop to source-aware scraping.

**Cron changes needed:** Yes, once scrape duration/failure risk grows.

**Done when:** New retailers can be added in batches with measured scrape reliability and affiliate coverage.

---

## Phase 6 — Cron/Backend Reliability

**Objective:** Make refresh automation production-grade for a monetized discount hub.

**Recommended tasks:**

- Add `/api/health`.
- Add scrape metrics.
- Persist last scrape summary.
- Track per-source/per-retailer failures.
- Add stale-data detection.
- Upgrade `discount-website-refresh` cronjob to alert only on meaningful problems.

**Recommended `/api/health` shape:**

```json
{
  "ok": true,
  "last_updated": "...",
  "deal_count": 123,
  "retailer_count": 42,
  "affiliate_supported_count": 31,
  "affiliate_deal_count": 78,
  "stale": false,
  "running": false,
  "last_error": null
}
```

**Cron should alert Phil if:**

- scrape fails
- scrape is stuck
- deal count drops below threshold
- affiliate coverage disappears after affiliate setup
- last update is stale
- too many retailers fail

**Cron should stay silent if:** healthy refresh succeeds.

**Backend changes needed:** Yes — health/metrics endpoint and persisted scrape status.

**Cron changes needed:** Yes — update `discount-website-refresh` after `/api/health` exists.

**Done when:** Automated refresh is reliable, quiet on success, and loud only on actionable problems.

---

## Cron Job Notes

### Existing Daily Buffer job

No immediate change needed. The Daily Buffer cronjob already reflects Phil’s updated X account limit of up to 25,000 characters and can use longer creative posts for ToneTraffic and Kalshi extension promotion.

If Deal Finder should be promoted daily later, create a separate Buffer campaign or add it as a deliberate third rotating topic — do not blend it into the Chrome-extension job accidentally.

### Existing `discount-website-refresh` job

Keep current behavior during Phases 0–3. Upgrade it in Phase 6 once backend health/metrics exist.

Current behavior is acceptable for the small app:

- POST `/api/scrape`
- poll `/api/status`
- silent on success
- report errors

Future behavior should use `/api/health` and alert only on meaningful production issues.

---

## Implementation Rule

Follow the phases in order. Do not start Phase 5 retailer expansion until Phases 0–4 are complete.

The highest-risk mistake would be scaling retailer count before deal normalization, analytics, affiliate handling, and registry architecture are in place.
