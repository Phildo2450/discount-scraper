"""
Coupon & Deals Scraper — Flask Backend
Sources: CouponFollow, Savings.com, RSS feeds (Slickdeals, 9to5Toys, DealNews)
Retailers: Amazon, Walmart, Target, Nike, H&M, Zara, ASOS, Best Buy, Newegg, B&H,
           DoorDash, Grubhub, Uber Eats
"""

import json
import os
import re
import time
import threading
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, send_from_directory

# ── Config ──────────────────────────────────────────────────────────────────

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEALS_FILE = os.path.join(BASE_DIR, "deals.json")

RETAILERS = [
    # Big-box
    {"name": "Amazon",    "domain": "amazon.com",         "slug": "amazon",    "category": "big-box",  "color": "#FF9900", "icon": "🛒"},
    {"name": "Walmart",   "domain": "walmart.com",        "slug": "walmart",   "category": "big-box",  "color": "#0071CE", "icon": "🏪"},
    {"name": "Target",    "domain": "target.com",         "slug": "target",    "category": "big-box",  "color": "#CC0000", "icon": "🎯"},
    # Fashion
    {"name": "Nike",      "domain": "nike.com",           "slug": "nike",      "category": "fashion",  "color": "#111111", "icon": "👟"},
    {"name": "H&M",       "domain": "hm.com",             "slug": "h-and-m",   "category": "fashion",  "color": "#E50010", "icon": "👗"},
    {"name": "Zara",      "domain": "zara.com",           "slug": "zara",      "category": "fashion",  "color": "#1A1A1A", "icon": "👘"},
    {"name": "ASOS",      "domain": "asos.com",           "slug": "asos",      "category": "fashion",  "color": "#2D3643", "icon": "🧥"},
    # Tech
    {"name": "Best Buy",  "domain": "bestbuy.com",        "slug": "best-buy",  "category": "tech",     "color": "#0046BE", "icon": "💻"},
    {"name": "Newegg",    "domain": "newegg.com",         "slug": "newegg",    "category": "tech",     "color": "#FF6600", "icon": "🖥️"},
    {"name": "B&H",       "domain": "bhphotovideo.com",   "slug": "b-and-h",   "category": "tech",     "color": "#002F65", "icon": "📷"},
    # Food & Delivery
    {"name": "DoorDash",  "domain": "doordash.com",       "slug": "doordash",  "category": "food",     "color": "#FF3008", "icon": "🚪"},
    {"name": "Grubhub",   "domain": "grubhub.com",        "slug": "grubhub",   "category": "food",     "color": "#F63440", "icon": "🍔"},
    {"name": "Uber Eats", "domain": "ubereats.com",       "slug": "uber-eats", "category": "food",     "color": "#06C167", "icon": "🛵"},
]

RETAILER_KEYWORDS = {r["name"]: r for r in RETAILERS}
# Also match partial / alternate names
KEYWORD_MAP = {
    "amazon": "Amazon", "walmart": "Walmart", "target": "Target",
    "nike": "Nike", "h&m": "H&M", "hm": "H&M",
    "zara": "Zara", "asos": "ASOS",
    "best buy": "Best Buy", "bestbuy": "Best Buy",
    "newegg": "Newegg",
    "b&h": "B&H", "bhphotovideo": "B&H", "b and h": "B&H",
    "doordash": "DoorDash", "door dash": "DoorDash",
    "grubhub": "Grubhub",
    "uber eats": "Uber Eats", "ubereats": "Uber Eats",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# Global scrape status
_scrape_status = {"running": False, "last_run": None, "message": ""}

# ── Helpers ──────────────────────────────────────────────────────────────────

def deal_id(*parts):
    return hashlib.md5("-".join(str(p) for p in parts).encode()).hexdigest()[:12]




def normalize_retailer_key(name):
    """Normalize a retailer name to a consistent lowercase key."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def build_deal(retailer, code, description, discount, source, url, deal_type=None):
    """Build a normalized deal dictionary with all required fields.

    Every scraper should use this to ensure consistent deal shape.
    """
    if deal_type is None:
        deal_type = "code" if code else "deal"
    return {
        "id": deal_id(retailer["name"], description[:40] if description else ""),
        "retailer": retailer["name"],
        "category": retailer.get("category", ""),
        "color": retailer.get("color", "#333333"),
        "icon": retailer.get("icon", ""),
        "code": code or "",
        "description": description or "",
        "discount": discount or "",
        "type": deal_type,
        "source": source,
        "url": url or "",
    }


def decorate_deal(deal):
    """Add computed/derived fields to a deal."""
    deal.setdefault("retailer_key", normalize_retailer_key(deal.get("retailer", "")))
    return deal


def validate_deal(deal):
    """Validate that a deal has the minimum required fields.

    Returns True if valid, False otherwise.
    """
    required = ("id", "retailer", "description", "source", "url")
    for field in required:
        if not deal.get(field):
            return False
    if not deal.get("code") and not deal.get("description"):
        return False
    return True


def load_deals():
    if os.path.exists(DEALS_FILE):
        try:
            with open(DEALS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"deals": [], "last_updated": None, "count": 0}


def save_deals(deals):
    data = {
        "deals": deals,
        "last_updated": datetime.now().isoformat(),
        "count": len(deals),
    }
    with open(DEALS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return data


def find_retailer(text):
    """Return retailer dict if any keyword matches text (case-insensitive)."""
    lower = text.lower()
    for kw, name in KEYWORD_MAP.items():
        if kw in lower:
            return RETAILER_KEYWORDS.get(name)
    return None


def safe_get(url, timeout=12, delay=0.4):
    """GET with retry and polite delay."""
    time.sleep(delay)
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  [WARN] GET {url} → {e}")
        return None


# ── Scrapers ─────────────────────────────────────────────────────────────────

def scrape_couponfollow(retailer):
    """couponfollow.com/site/{domain}"""
    url = f"https://couponfollow.com/site/{retailer['domain']}"
    deals = []
    r = safe_get(url)
    if not r:
        return deals

    soup = BeautifulSoup(r.text, "html.parser")

    # Strategy 1 — data-code attribute on any element
    for el in soup.select("[data-code]"):
        code = el.get("data-code", "").strip()
        if not code or len(code) > 30:
            continue
        desc = (
            el.select_one(".title, .offer-title, h3, h2, [class*='title']") or
            el.select_one("p, [class*='desc']")
        )
        discount = el.select_one(".discount, .badge, [class*='discount'], [class*='saving'], [class*='off']")
        deal = build_deal(
            retailer=retailer,
            code=code,
            description=desc.get_text(strip=True) if desc else "Discount offer",
            discount=discount.get_text(strip=True) if discount else "",
            source="CouponFollow",
            url=f"https://couponfollow.com/site/{retailer['domain']}",
            deal_type="code",
        )
        deal = decorate_deal(deal)
        if validate_deal(deal):
            deals.append(deal)
        if len(deals) >= 6:
            break

    # Strategy 2 — look for coupon containers without data-code
    if not deals:
        containers = soup.select(
            ".coupon, .offer, [class*='coupon-item'], [class*='deal-card'], "
            "[class*='offer-item'], article[class*='coupon']"
        )
        for el in containers[:6]:
            # Look for a code-like string: 4-20 uppercase alphanumeric chars
            code_el = el.select_one(
                ".code, .coupon-code, [class*='code'], input[type='text'], "
                "span[class*='code'], button[class*='code']"
            )
            code = ""
            if code_el:
                code = code_el.get("value") or code_el.get_text(strip=True)
                code = re.sub(r"\s+", "", code).upper()
                if len(code) > 25:
                    code = ""

            desc = el.select_one("h3, h2, .title, [class*='title']")
            discount = el.select_one("[class*='discount'], [class*='saving'], [class*='badge'], [class*='off']")

            description = desc.get_text(strip=True) if desc else el.get_text(strip=True)[:80]
            if not description:
                continue

            deal = build_deal(
                retailer=retailer,
                code=code,
                description=description,
                discount=discount.get_text(strip=True) if discount else "",
                source="CouponFollow",
                url=f"https://couponfollow.com/site/{retailer['domain']}",
            )
            deal = decorate_deal(deal)
            if validate_deal(deal):
                deals.append(deal)

    print(f"  CouponFollow → {retailer['name']}: {len(deals)} deals")
    return deals


def scrape_savings_com(retailer):
    """savings.com/coupons/{slug}-coupons/"""
    url = f"https://www.savings.com/coupons/{retailer['slug']}-coupons/"
    deals = []
    r = safe_get(url)
    if not r:
        return deals

    soup = BeautifulSoup(r.text, "html.parser")

    for el in soup.select("[data-coupon-code], [data-code]"):
        code = (el.get("data-coupon-code") or el.get("data-code", "")).strip()
        if not code:
            continue
        desc = el.select_one("h3, h2, .title, [class*='title'], p")
        discount = el.select_one("[class*='discount'], [class*='saving'], [class*='badge']")
        deal = build_deal(
            retailer=retailer,
            code=code,
            description=desc.get_text(strip=True) if desc else "Special offer",
            discount=discount.get_text(strip=True) if discount else "",
            source="Savings.com",
            url=url,
            deal_type="code",
        )
        deal = decorate_deal(deal)
        if validate_deal(deal):
            deals.append(deal)
        if len(deals) >= 4:
            break

    print(f"  Savings.com → {retailer['name']}: {len(deals)} deals")
    return deals


def scrape_couponcabin(retailer):
    """couponcabin.com/coupons/{slug}/"""
    url = f"https://www.couponcabin.com/coupons/{retailer['slug']}/"
    deals = []
    r = safe_get(url)
    if not r:
        return deals

    soup = BeautifulSoup(r.text, "html.parser")

    for el in soup.select(".coupon-code-wrap, [class*='coupon'][data-code], [data-code]"):
        code = el.get("data-code", "").strip()
        if not code:
            inp = el.select_one("input")
            if inp:
                code = inp.get("value", "").strip()
        if not code or len(code) > 25:
            continue
        desc = el.select_one("h3, h2, .title, p")
        deal = build_deal(
            retailer=retailer,
            code=code,
            description=desc.get_text(strip=True) if desc else "Promo code",
            discount="",
            source="CouponCabin",
            url=url,
            deal_type="code",
        )
        deal = decorate_deal(deal)
        if validate_deal(deal):
            deals.append(deal)
        if len(deals) >= 4:
            break

    print(f"  CouponCabin → {retailer['name']}: {len(deals)} deals")
    return deals


def scrape_rss_feed(feed_url, source_name, max_items=60):
    """Parse an RSS/Atom feed and match items to retailers."""
    deals = []
    r = safe_get(feed_url, delay=0.5)
    if not r:
        return deals

    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        return deals

    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # RSS 2.0
    items = root.findall(".//item")
    # Atom
    if not items:
        items = root.findall(".//atom:entry", ns) or root.findall(".//entry")

    for item in items[:max_items]:
        # Title
        title_el = item.find("title")
        title = title_el.text if title_el is not None else ""
        if not title:
            title = (item.find("atom:title", ns) or item.find("title") or type("", (), {"text": ""})()).text or ""

        # Description / summary
        desc_el = item.find("description") or item.find("summary") or item.find("atom:summary", ns)
        raw_desc = desc_el.text or "" if desc_el is not None else ""
        # Strip HTML tags
        desc = BeautifulSoup(raw_desc, "html.parser").get_text(strip=True)[:200] if raw_desc else ""

        # Link
        link_el = item.find("link")
        link = link_el.text if link_el is not None and link_el.text else ""

        combined = f"{title} {desc}".lower()
        retailer = find_retailer(combined)
        if not retailer:
            continue

        # Look for a promo code pattern in title/desc
        code_match = re.search(r"\b(code|promo|coupon)[:\s]+([A-Z0-9]{4,20})\b", title, re.IGNORECASE)
        code = code_match.group(2).upper() if code_match else ""

        # Extract discount string like "20% off", "$10 off"
        disc_match = re.search(r"(\$?\d+%?\s*off|\d+%\s*off)", title, re.IGNORECASE)
        discount = disc_match.group(0).title() if disc_match else ""

        deal = build_deal(
            retailer=retailer,
            code=code,
            description=title[:120],
            discount=discount,
            source="Unknown",
            url=link,
        )
        deal = decorate_deal(deal)
        if validate_deal(deal):
            deals.append(deal)

    print(f"  RSS ({source_name}): matched {len(deals)} deals to retailers")
    return deals


RSS_FEEDS = [
    ("https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1", "Slickdeals"),
    ("https://9to5toys.com/feed/", "9to5Toys"),
    ("https://9to5mac.com/feed/", "9to5Mac"),
    ("https://dealnews.com/rss/", "DealNews"),
    ("https://www.bensdeals.com/rss/", "Brad's Deals"),
]


def scrape_retailer(retailer):
    """Try all coupon sources for a single retailer, return best results."""
    deals = []

    # Try CouponFollow first
    deals = scrape_couponfollow(retailer)

    # If nothing, try Savings.com
    if not deals:
        deals = scrape_savings_com(retailer)

    # If still nothing, try CouponCabin
    if not deals:
        deals = scrape_couponcabin(retailer)

    return deals


def scrape_all():
    """Full scrape: all retailers + RSS feeds. Returns list of deal dicts."""
    global _scrape_status
    _scrape_status["running"] = True
    _scrape_status["message"] = "Scraping coupon sites…"
    print("\n=== Starting scrape ===")

    all_deals = []
    seen_ids = set()

    def add_deals(new_deals):
        for d in new_deals:
            if d["id"] not in seen_ids:
                seen_ids.add(d["id"])
                all_deals.append(d)

    # Scrape per-retailer coupon sites (max 4 parallel to be polite)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(scrape_retailer, r): r for r in RETAILERS}
        for future in as_completed(futures):
            try:
                add_deals(future.result())
            except Exception as e:
                print(f"  [ERROR] retailer scrape: {e}")

    _scrape_status["message"] = "Scraping deal feeds…"

    # Scrape RSS feeds sequentially (fast)
    for feed_url, source_name in RSS_FEEDS:
        try:
            add_deals(scrape_rss_feed(feed_url, source_name))
        except Exception as e:
            print(f"  [ERROR] RSS {source_name}: {e}")

    # Sort: codes first, then deals; within each group sort by retailer name
    all_deals.sort(key=lambda d: (0 if d["type"] == "code" else 1, d["retailer"]))

    data = save_deals(all_deals)
    _scrape_status["running"] = False
    _scrape_status["last_run"] = data["last_updated"]
    _scrape_status["message"] = f"Done — {len(all_deals)} deals found"
    print(f"=== Scrape complete: {len(all_deals)} deals ===\n")
    return data


# ── Flask Routes ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/deals")
def api_deals():
    data = load_deals()
    # Build retailer domain lookup
    domain_map = {r["name"].lower(): r["domain"] for r in RETAILERS}
    # Ensure each deal has a url field pointing to the retailer website
    deals = data.get("deals", []) if isinstance(data, dict) else []
    for deal in deals:
        if not deal.get("url"):
            retailer = deal.get("retailer", "")
            domain = domain_map.get(retailer.lower(), "")
            if domain:
                deal["url"] = f"https://www.{domain}"
    return jsonify(data)


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    if _scrape_status["running"]:
        return jsonify({"status": "already_running", "message": "Scrape already in progress"}), 202

    def run():
        scrape_all()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return jsonify({"status": "started", "message": "Scrape started in background"}), 202


@app.route("/api/status")
def api_status():
    return jsonify(_scrape_status)


@app.route("/api/retailers")
def api_retailers():
    return jsonify(RETAILERS)


# ── Entry point ───────────────────────────────────────────────────────────────


@app.route("/api/categories")
def api_categories():
    data = load_deals()
    deals = data.get("deals", [])
    cat_meta = {
        "services": {"color": "#8338EC", "icon": "\ud83d\udd27", "label": "Services"},
        "electronics": {"color": "#8338EC", "icon": "\ud83d\udcfa", "label": "Electronics"},
        "fashion": {"color": "#FF006E", "icon": "\ud83d\udc57", "label": "Fashion"},
        "beauty": {"color": "#FF006E", "icon": "\ud83d\udc84", "label": "Beauty"},
        "home": {"color": "#3A86FF", "icon": "\ud83c\udfe0", "label": "Home"},
        "food": {"color": "#FB5607", "icon": "\ud83c\udf54", "label": "Food"},
        "travel": {"color": "#8338EC", "icon": "\u2708\ufe0f", "label": "Travel"},
        "health": {"color": "#06D6A0", "icon": "\ud83d\udc8a", "label": "Health"},
    }
    cat_counts = {}
    for deal in deals:
        cat = deal.get("category", "services").lower()
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    result = []
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        meta = cat_meta.get(cat, {"color": "#8338EC", "icon": "\ud83c\udfaf", "label": cat.title()})
        result.append({"category": cat, "color": meta["color"], "count": count, "icon": meta["icon"], "label": meta["label"]})
    return jsonify(result)


@app.route("/api/deals/trending")
def api_deals_trending():
    data = load_deals()
    deals = data.get("deals", [])
    def get_discount(d):
        import re as _re
        match = _re.search(r"(\d+)%", d.get("description", ""))
        return int(match.group(1)) if match else 0
    trending = sorted(deals, key=get_discount, reverse=True)[:10]
    domain_map = {r["name"].lower(): r["domain"] for r in RETAILERS}
    for deal in trending:
        if not deal.get("url"):
            domain = domain_map.get(deal.get("retailer", "").lower(), "")
            if domain:
                deal["url"] = f"https://www.{domain}"
    return jsonify(trending)


@app.route("/api/deals/featured")
def api_deals_featured():
    data = load_deals()
    deals = data.get("deals", [])
    if deals:
        domain_map = {r["name"].lower(): r["domain"] for r in RETAILERS}
        for deal in deals:
            if deal.get("code"):
                if not deal.get("url"):
                    domain = domain_map.get(deal.get("retailer", "").lower(), "")
                    if domain:
                        deal["url"] = f"https://www.{domain}"
                return jsonify(deal)
        deal = deals[0]
        if not deal.get("url"):
            domain = domain_map.get(deal.get("retailer", "").lower(), "")
            if domain:
                deal["url"] = f"https://www.{domain}"
        return jsonify(deal)
    return jsonify(None)


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    from flask import request
    data = request.get_json(silent=True) or {}
    deal_id = data.get("dealId", "")
    feedback_type = data.get("type", "")
    return jsonify({"status": "ok", "dealId": deal_id, "type": feedback_type})



@app.route("/manifest.json")
def manifest():
    return send_from_directory(".", "manifest.json", mimetype="application/manifest+json")


if __name__ == "__main__":
    # Run an initial scrape if no cached data exists
    if not os.path.exists(DEALS_FILE):
        print("No cached data — running initial scrape…")
        threading.Thread(target=scrape_all, daemon=True).start()
    app.run(host="127.0.0.1", port=5050, debug=False)