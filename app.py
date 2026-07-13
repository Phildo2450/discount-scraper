"""
Deal Drop / RealDiscountCodes backend.

Security and trust policy:
- Publish only deals/codes from official retailer domains or pre-approved official X accounts.
- Hide public deals once their source check is older than the freshness window.
- Reject third-party coupon aggregators, RSS deal blogs, and untrusted social accounts.
"""

import json
import os
import re
import time
import threading
import hashlib
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, send_from_directory, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging
from urllib.parse import urlparse

# --- Validation & Scheduling Setup ---
validation_logger = logging.getLogger('code_validation')
validation_logger.setLevel(logging.INFO)
_log_handler = logging.StreamHandler()
_log_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s'))
validation_logger.addHandler(_log_handler)

INVALID_CODES_LOG = []  # Stores codes that failed validation


# ── Config ──────────────────────────────────────────────────────────────────

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEALS_FILE = os.path.join(BASE_DIR, "deals.json")

RETAILERS_FILE = os.path.join(BASE_DIR, "retailers_official.json")
FRESHNESS_HOURS = int(os.environ.get("DEALDROP_FRESHNESS_HOURS", "3"))
FRESHNESS_WINDOW = timedelta(hours=FRESHNESS_HOURS)
MAX_PROMO_PAGES_PER_RETAILER = int(os.environ.get("DEALDROP_MAX_PROMO_PAGES", "4"))
MAX_DEALS_PER_RETAILER = int(os.environ.get("DEALDROP_MAX_DEALS_PER_RETAILER", "6"))
SCRAPE_BATCH_SIZE = int(os.environ.get("DEALDROP_SCRAPE_BATCH_SIZE", "12"))
TRUSTED_SOURCE_TYPES = {"official_site", "official_x", "affiliate_feed"}
BLOCKED_SOURCE_HOST_KEYWORDS = (
    "couponfollow", "savings.com", "couponcabin", "retailmenot", "slickdeals",
    "dealnews", "bensdeals", "9to5toys", "9to5mac", "coupon", "dealsplus",
)

def utcnow():
    return datetime.now(timezone.utc)

def iso_now():
    return utcnow().isoformat()

def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None

def host_matches_domain(host, domain):
    host = (host or "").lower().strip().rstrip(".")
    domain = (domain or "").lower().strip().rstrip(".")
    return host == domain or host.endswith("." + domain)

def allowed_source_host(url, retailer):
    try:
        host = urlparse(url).netloc.lower().split(":", 1)[0]
    except Exception:
        return False
    if not host:
        return False
    domain = retailer.get("domain", "")
    allowed = set(retailer.get("allowed_domains") or []) | {domain, f"www.{domain}"}
    return any(host_matches_domain(host, d) for d in allowed if d)

def load_official_retailers():
    if os.path.exists(RETAILERS_FILE):
        with open(RETAILERS_FILE, encoding="utf-8") as f:
            retailers = json.load(f)
    else:
        retailers = RETAILERS
    for r in retailers:
        domain = r.get("domain", "").lower().strip()
        r.setdefault("allowed_domains", [domain, f"www.{domain}"])
        r.setdefault("promo_paths", ["/", "/sale", "/deals", "/offers", "/coupons", "/promo-code"])
        r.setdefault("official_x_handles", [])
        r.setdefault("source_policy", "official_site_or_official_x_only")
    return retailers

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
    {"name": "CVS",         "domain": "cvs.com",            "color": "#CC0000", "icon": "\U0001f48a", "category": "health",  "slug": "cvs"},
    {"name": "Macys",       "domain": "macys.com",          "color": "#E21A2C", "icon": "\U0001f6cd", "category": "fashion", "slug": "macys"},
]

RETAILERS = load_official_retailers()
RETAILER_KEYWORDS = {r["name"]: r for r in RETAILERS}
KEYWORD_MAP = {}
for _r in RETAILERS:
    names = {_r.get("name", ""), _r.get("slug", ""), _r.get("domain", "").split(".")[0]}
    names.update(_r.get("keywords") or [])
    for _name in names:
        if _name:
            KEYWORD_MAP[_name.lower()] = _r["name"]

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
    return hashlib.sha256("-".join(str(p) for p in parts).encode()).hexdigest()[:12]




def normalize_retailer_key(name):
    """Normalize a retailer name to a consistent lowercase key."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def build_deal(retailer=None, code="", description="", discount="", source="", url="", deal_type=None, **legacy):
    """Build a normalized deal dictionary with official-source provenance fields.

    The legacy keyword path keeps old tests/helpers from crashing, but production
    scrapers pass a retailer dict and official source metadata.
    """
    if retailer is None or isinstance(retailer, str):
        retailer_name = retailer or legacy.get("retailer", "")
        retailer = find_retailer(retailer_name) or {
            "name": retailer_name,
            "domain": urlparse(legacy.get("url", url) or "").netloc.replace("www.", ""),
            "category": legacy.get("category", ""),
            "color": "#333333",
            "icon": "",
        }
    description = description or legacy.get("title", "") or legacy.get("description", "")
    code = (code if code is not None else legacy.get("code", "")) or ""
    discount = discount or legacy.get("discount", "") or ""
    url = url or legacy.get("url", "") or ""
    if deal_type is None:
        deal_type = "code" if code else "deal"
    source_type = legacy.get("source_type") or "official_site"
    checked_at = legacy.get("source_checked_at") or iso_now()
    return {
        "id": deal_id(retailer.get("name", ""), code, description[:80], url),
        "title": description,
        "retailer": retailer.get("name", ""),
        "category": retailer.get("category", ""),
        "color": retailer.get("color", "#333333"),
        "icon": retailer.get("icon", ""),
        "domain": retailer.get("domain", ""),
        "code": code.strip().upper(),
        "description": description or "",
        "discount": discount or "",
        "type": deal_type,
        "source": source or retailer.get("name", ""),
        "source_type": source_type,
        "source_url": url,
        "source_checked_at": checked_at,
        "validated_at": checked_at,
        "fresh_until": (parse_dt(checked_at) + FRESHNESS_WINDOW).isoformat() if parse_dt(checked_at) else "",
        "official_source": True,
        "isVerified": True,
        "confidence_score": legacy.get("confidence_score", 90 if code else 75),
        "url": url or f"https://www.{retailer.get('domain', '')}",
    }


def decorate_deal(deal):
    """Add computed/derived fields to a deal."""
    deal.setdefault("retailer_key", normalize_retailer_key(deal.get("retailer", "")))
    return deal


def validate_deal(deal):
    """Validate official provenance, freshness, and minimum public fields."""
    required = ("id", "retailer", "description", "source", "url", "source_url", "source_checked_at")
    if any(not deal.get(field) for field in required):
        return False
    if deal.get("source_type") not in TRUSTED_SOURCE_TYPES:
        return False
    if deal.get("official_source") is not True:
        return False
    checked = parse_dt(deal.get("source_checked_at"))
    if not checked or utcnow() - checked > FRESHNESS_WINDOW:
        return False
    retailer = RETAILER_KEYWORDS.get(deal.get("retailer")) or find_retailer(deal.get("retailer", ""))
    if not retailer:
        return False
    if deal.get("source_type") == "official_site" and not allowed_source_host(deal.get("source_url", ""), retailer):
        return False
    if deal.get("source_type") == "official_x":
        handle = (deal.get("official_x_handle") or "").strip().lstrip("@").lower()
        allowed_handles = {h.strip().lstrip("@").lower() for h in retailer.get("official_x_handles", [])}
        if not handle or handle not in allowed_handles:
            return False
    if deal.get("code"):
        # Codes need explicit coupon/promo context to avoid publishing SKUs or random tokens.
        context = f"{deal.get('description','')} {deal.get('discount','')}".lower()
        if not re.search(r"(code|promo|coupon|checkout|use\s+code|enter\s+code|off|shipping|bogo|save)", context):
            return False
    return True


def load_deals():
    if os.path.exists(DEALS_FILE):
        try:
            with open(DEALS_FILE) as f:
                return json.load(f)
        except Exception as e:
            validation_logger.warning("Failed to load deals file: %s", e)
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



CODE_CONTEXT_RE = re.compile(r"(?:use|enter|apply)?\s*(?:promo|coupon|discount)?\s*code\s*[:\-]?\s*([A-Z0-9][A-Z0-9_\-]{3,24})", re.I)
GENERIC_CODE_RE = re.compile(r"\b[A-Z][A-Z0-9_\-]{4,20}\b")
DISCOUNT_RE = re.compile(r"(\$\s?\d+\s*off|\d+\s?%\s*off|free\s+shipping|bogo|buy\s+one|get\s+one|save\s+\$?\d+)", re.I)
OFFER_WORD_RE = re.compile(r"(promo|coupon|discount|sale|offer|deal|clearance|code|checkout|free shipping|bogo|save)", re.I)


def official_url_for(retailer, path):
    path = path or "/"
    if not path.startswith("/"):
        path = "/" + path
    domain = retailer.get("domain", "").lower().strip()
    return f"https://www.{domain}{path}"


def safe_get_official(url, retailer, timeout=14, delay=0.25):
    if not allowed_source_host(url, retailer):
        validation_logger.warning("Blocked non-official URL for %s: %s", retailer.get("name"), url)
        return None
    time.sleep(delay)
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if not allowed_source_host(r.url, retailer):
            validation_logger.warning("Blocked redirect off official domain for %s: %s -> %s", retailer.get("name"), url, r.url)
            return None
        if r.status_code >= 400:
            return None
        ctype = r.headers.get("content-type", "")
        if "text/html" not in ctype and "text/plain" not in ctype and ctype:
            return None
        return r
    except Exception as e:
        validation_logger.debug("Official GET failed for %s %s: %s", retailer.get("name"), url, e)
        return None


def clean_text(value, limit=180):
    value = re.sub(r"\s+", " ", value or "").strip()
    return value[:limit]


def infer_discount(text):
    m = DISCOUNT_RE.search(text or "")
    return m.group(1).title().replace("  ", " ") if m else ""


def extract_candidate_blocks(soup):
    selectors = [
        "[data-code]", "[data-coupon]", "[data-promo-code]", "[class*='coupon']",
        "[class*='promo']", "[class*='offer']", "[class*='deal']", "article", "section", "li"
    ]
    seen = set()
    for el in soup.select(",".join(selectors))[:300]:
        text = clean_text(el.get_text(" ", strip=True), 500)
        if not text or text in seen or not OFFER_WORD_RE.search(text):
            continue
        seen.add(text)
        yield el, text


def extract_codes_from_text(text):
    """Extract only explicit official promo/coupon code mentions.

    This intentionally does not harvest generic uppercase tokens; official pages
    often contain SKUs, model names, stock tickers, and product IDs that look like
    coupon codes. A token must be directly introduced as a promo/coupon/code.
    """
    codes = []
    for m in CODE_CONTEXT_RE.finditer(text or ""):
        code = m.group(1).upper().strip('.,;:!?)"]')
        if 4 <= len(code) <= 24 and not code.isdigit() and code not in codes:
            codes.append(code)
    return codes


def official_site_home_deal(retailer, source_url):
    checked = iso_now()
    return decorate_deal(build_deal(
        retailer=retailer,
        code="",
        description=f"Official {retailer['name']} offers and sale page checked within {FRESHNESS_HOURS} hours.",
        discount="Official Offers",
        source=retailer["name"],
        url=source_url,
        deal_type="deal",
        source_type="official_site",
        source_checked_at=checked,
        confidence_score=75,
    ))


def scrape_official_site(retailer):
    """Scrape only pre-approved official retailer pages for fresh codes/offers."""
    deals = []
    paths = retailer.get("promo_paths") or ["/", "/sale", "/deals", "/offers", "/coupons"]
    for path in paths[:MAX_PROMO_PAGES_PER_RETAILER]:
        url = official_url_for(retailer, path)
        r = safe_get_official(url, retailer)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        checked = iso_now()
        found_on_page = 0
        for _, block_text in extract_candidate_blocks(soup):
            discount = infer_discount(block_text)
            codes = extract_codes_from_text(block_text)
            if codes:
                for code in codes[:2]:
                    deal = build_deal(
                        retailer=retailer,
                        code=code,
                        description=clean_text(block_text, 140),
                        discount=discount or "Promo Code",
                        source=retailer["name"],
                        url=r.url,
                        deal_type="code",
                        source_type="official_site",
                        source_checked_at=checked,
                        confidence_score=95,
                    )
                    deal = decorate_deal(deal)
                    if validate_deal(deal):
                        deals.append(deal); found_on_page += 1
            elif discount:
                deal = build_deal(
                    retailer=retailer,
                    code="",
                    description=clean_text(block_text, 140),
                    discount=discount,
                    source=retailer["name"],
                    url=r.url,
                    deal_type="deal",
                    source_type="official_site",
                    source_checked_at=checked,
                    confidence_score=82,
                )
                deal = decorate_deal(deal)
                if validate_deal(deal):
                    deals.append(deal); found_on_page += 1
            if len(deals) >= MAX_DEALS_PER_RETAILER:
                break
        if not found_on_page and path in ("/", ""):
            home = official_site_home_deal(retailer, r.url)
            if validate_deal(home):
                deals.append(home)
        if len(deals) >= MAX_DEALS_PER_RETAILER:
            break
    validation_logger.info("Official site → %s: %s deals", retailer.get("name"), len(deals))
    return deals[:MAX_DEALS_PER_RETAILER]


def scrape_official_x(retailer):
    """Optional official X ingestion via X API v2 bearer token. Disabled unless X_BEARER_TOKEN is set."""
    token = os.environ.get("X_BEARER_TOKEN", "").strip()
    handles = [h.strip().lstrip("@") for h in retailer.get("official_x_handles", []) if h.strip()]
    if not token or not handles:
        return []
    query_handles = " OR ".join(f"from:{h}" for h in handles[:8])
    query = f"({query_handles}) (code OR promo OR coupon OR discount OR sale OR \"free shipping\") -is:retweet"
    params = {
        "query": query,
        "max_results": "10",
        "tweet.fields": "created_at,author_id",
        "expansions": "author_id",
        "user.fields": "username",
    }
    try:
        r = requests.get(
            "https://api.x.com/2/tweets/search/recent",
            headers={"Authorization": f"Bearer {token}", "User-Agent": HEADERS["User-Agent"]},
            params=params,
            timeout=12,
        )
        if r.status_code != 200:
            validation_logger.warning("X recent search failed for %s: HTTP %s", retailer.get("name"), r.status_code)
            return []
        payload = r.json()
    except Exception as e:
        validation_logger.warning("X recent search error for %s: %s", retailer.get("name"), e)
        return []
    deals = []
    checked = iso_now()
    users = {u.get("id"): u.get("username", "") for u in payload.get("includes", {}).get("users", [])}
    for post in payload.get("data", []):
        txt = post.get("text", "")
        codes = extract_codes_from_text(txt)
        discount = infer_discount(txt)
        if not codes and not discount:
            continue
        handle = users.get(post.get("author_id")) or (handles[0] if len(handles) == 1 else "")
        handle = handle.strip().lstrip("@")
        if handle.lower() not in {h.lower() for h in handles}:
            continue
        post_url = f"https://x.com/{handle}/status/{post.get('id')}"
        for code in codes or [""]:
            deal = build_deal(
                retailer=retailer, code=code, description=clean_text(txt, 150),
                discount=discount or ("Official X Offer" if not code else "Promo Code"),
                source=f"Official X @{handle}", url=post_url, deal_type="code" if code else "deal",
                source_type="official_x", source_checked_at=checked, confidence_score=90,
            )
            deal["official_x_handle"] = handle
            deal = decorate_deal(deal)
            if validate_deal(deal):
                deals.append(deal)
    return deals[:MAX_DEALS_PER_RETAILER]


def scrape_retailer(retailer):
    """Official-only ingestion for one retailer."""
    return dedupe_deals(scrape_official_site(retailer) + scrape_official_x(retailer))[:MAX_DEALS_PER_RETAILER]


def dedupe_deals(deals):
    seen = set(); out = []
    for deal in deals:
        if deal.get("code"):
            key = (deal.get("retailer_key"), deal.get("code"))
        else:
            key = (deal.get("retailer_key"), deal.get("description", "")[:80], deal.get("source_url"))
        if key in seen:
            continue
        seen.add(key); out.append(deal)
    return out


def is_fresh_official_deal(deal):
    return validate_deal(deal)


def public_deals():
    data = load_deals()
    deals = data.get("deals", []) if isinstance(data, dict) else []
    return [decorate_deal(d) for d in deals if is_fresh_official_deal(d)]

# --- Official-source validation logic ---
def validate_code_against_aggregators(code, retailer):
    """Deprecated compatibility shim. Third-party aggregators are not trusted."""
    return False


def validate_and_filter_deals(new_deals):
    """Return only fresh, official-source deals/codes."""
    global INVALID_CODES_LOG
    validated_deals = []
    invalid_deals = []
    for deal in new_deals:
        if is_fresh_official_deal(deal):
            deal["validated"] = True
            deal["isVerified"] = True
            deal.setdefault("validated_at", iso_now())
            validated_deals.append(deal)
        else:
            invalid_entry = {
                "code": deal.get("code", ""),
                "retailer": deal.get("retailer", ""),
                "description": deal.get("description", ""),
                "source_url": deal.get("source_url", deal.get("url", "")),
                "reason": "Rejected by official-source/freshness gate",
                "scraped_at": iso_now(),
            }
            INVALID_CODES_LOG.append(invalid_entry)
            invalid_deals.append(deal)
    validation_logger.info("Official validation complete: %s valid, %s rejected", len(validated_deals), len(invalid_deals))
    return dedupe_deals(validated_deals)


def scrape_all():
    """Scrape a rolling batch of official retailer sources and publish only fresh official deals."""
    global _scrape_status
    _scrape_status = {"running": True, "last_run": _scrape_status.get("last_run"), "message": "Official-source scrape in progress..."}
    all_new_deals = []
    state = load_deals()
    cursor = int(state.get("cursor", 0)) if isinstance(state, dict) else 0
    batch = [RETAILERS[(cursor + i) % len(RETAILERS)] for i in range(min(SCRAPE_BATCH_SIZE, len(RETAILERS)))]
    next_cursor = (cursor + len(batch)) % len(RETAILERS)

    with ThreadPoolExecutor(max_workers=min(6, len(batch) or 1)) as executor:
        futures = {executor.submit(scrape_retailer, r): r for r in batch}
        for fut in as_completed(futures):
            retailer = futures[fut]
            try:
                all_new_deals.extend(fut.result())
            except Exception as e:
                validation_logger.warning("Error scraping %s: %s", retailer.get("name"), e)

    validation_logger.info("Starting official validation of %s candidates...", len(all_new_deals))
    validated_deals = validate_and_filter_deals(all_new_deals)

    existing = state.get("deals", []) if isinstance(state, dict) else []
    replacement_keys = {d.get("retailer_key") for d in validated_deals}
    kept = [d for d in existing if d.get("retailer_key") not in replacement_keys and is_fresh_official_deal(d)]
    final_deals = dedupe_deals(kept + validated_deals)
    saved = save_deals(final_deals)
    saved["cursor"] = next_cursor
    saved["last_batch"] = [r.get("name") for r in batch]
    saved["freshness_hours"] = FRESHNESS_HOURS
    with open(DEALS_FILE, "w", encoding="utf-8") as f:
        json.dump(saved, f, indent=2)

    _scrape_status = {
        "running": False,
        "last_run": iso_now(),
        "message": f"Completed official scrape: {len(validated_deals)} fresh official deals published; {len(INVALID_CODES_LOG)} candidates rejected",
        "last_batch": [r.get("name") for r in batch],
        "freshness_hours": FRESHNESS_HOURS,
        "next_cursor": next_cursor,
    }
    return validated_deals


@app.route("/")
def index():
    return render_template("index.html", retailer_count=len(RETAILERS))


@app.route("/api/deals")
def api_deals():
    deals = public_deals()
    search = (request.args.get("search") or "").strip().lower()
    category = (request.args.get("category") or "").strip().lower()
    deal_type = (request.args.get("type") or "").strip().lower()
    sort = (request.args.get("sort") or "newest").strip().lower()
    page = max(1, int(request.args.get("page", 1)))
    limit = min(100, max(1, int(request.args.get("limit", 100))))

    if search:
        deals = [d for d in deals if search in " ".join([d.get("retailer", ""), d.get("description", ""), d.get("code", ""), d.get("source", "")]).lower()]
    if category:
        deals = [d for d in deals if d.get("category", "").lower() == category]
    if deal_type:
        deals = [d for d in deals if d.get("type", "").lower() == deal_type]

    if sort in {"discount", "best"}:
        deals.sort(key=lambda d: int((re.search(r"(\d+)", d.get("discount", "")) or [0, 0])[1]), reverse=True)
    else:
        deals.sort(key=lambda d: d.get("source_checked_at", ""), reverse=True)

    total = len(deals)
    pages = max(1, (total + limit - 1) // limit)
    start = (page - 1) * limit
    sliced = deals[start:start + limit]
    return jsonify({
        "deals": sliced,
        "page": page,
        "pages": pages,
        "limit": limit,
        "total": total,
        "total_deals": total,
        "total_codes": sum(1 for d in deals if d.get("code")),
        "freshness_hours": FRESHNESS_HOURS,
    })


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


@app.route("/healthz")
def healthz():
    """Lightweight endpoint for uptime checks."""
    return jsonify({"status": "ok"})


@app.route("/api/retailers")
def api_retailers():
    return jsonify(RETAILERS)


# ── Entry point ───────────────────────────────────────────────────────────────


@app.route("/api/categories")
def api_categories():
    deals = public_deals()
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
    deals = public_deals()
    def get_discount(d):
        match = re.search(r"(\d+)", d.get("discount", "") or d.get("description", ""))
        return int(match.group(1)) if match else 0
    trending = sorted(deals, key=lambda d: (bool(d.get("code")), get_discount(d), d.get("source_checked_at", "")), reverse=True)[:10]
    for d in trending:
        d["isTrending"] = True
    return jsonify({"deals": trending})


@app.route("/api/deals/featured")
def api_deals_featured():
    deals = public_deals()
    coded = [d for d in deals if d.get("code")]
    deal = (coded or deals or [None])[0]
    return jsonify({"deal": deal})


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    data = request.get_json(silent=True) or {}
    deal_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(data.get("dealId", "")))[:64]
    feedback_type = str(data.get("type", ""))[:16]
    if feedback_type not in {"worked", "failed", "yes", "no", "true", "false"}:
        feedback_type = "unknown"
    return jsonify({"status": "ok", "dealId": deal_id, "type": feedback_type})


@app.route("/api/source-status")
def api_source_status():
    deals = public_deals()
    by_retailer = {}
    for r in RETAILERS:
        by_retailer[r["slug"]] = {
            "name": r["name"], "domain": r["domain"],
            "official_x_handles": r.get("official_x_handles", []),
            "promo_paths": r.get("promo_paths", []),
            "fresh_deals": 0, "fresh_codes": 0,
        }
    for d in deals:
        key = d.get("retailer_key")
        for slug, item in by_retailer.items():
            if normalize_retailer_key(item["name"]) == key:
                item["fresh_deals"] += 1
                if d.get("code"):
                    item["fresh_codes"] += 1
                break
    return jsonify({"freshness_hours": FRESHNESS_HOURS, "retailers": list(by_retailer.values())})


@app.route("/manifest.json")
def manifest():
    return send_from_directory(".", "manifest.json", mimetype="application/manifest+json")



# --- APScheduler: Automated 15-minute rolling official-source scraping schedule ---
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=scrape_all,
    trigger=IntervalTrigger(minutes=15),
    id='scheduled_scrape',
    name='Scrape a rolling batch of official retailer sources every 15 minutes',
    replace_existing=True
)
scheduler.start()
validation_logger.info("APScheduler started: rolling official-source scrape every 15 minutes")

# API endpoint to view invalid/rejected codes
@app.route("/api/invalid-codes")
def api_invalid_codes():
    return jsonify(INVALID_CODES_LOG[-100:])  # Return last 100 invalid codes


if __name__ == "__main__":
    # Run an initial scrape if no cached data exists
    if not os.path.exists(DEALS_FILE):
        print("No cached data — running initial scrape…")
        threading.Thread(target=scrape_all, daemon=True).start()
    app.run(host="127.0.0.1", port=5050, debug=False)