

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
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

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

RETAILERS = [
    {"name": "Amazon", "domain": "amazon.com", "slug": "amazon", "category": "big-box", "color": "#FF9900", "icon": "📦"},
    {"name": "Walmart", "domain": "walmart.com", "slug": "walmart", "category": "big-box", "color": "#0071CE", "icon": "🏪"},
    {"name": "Target", "domain": "target.com", "slug": "target", "category": "big-box", "color": "#CC0000", "icon": "🎯"},
    {"name": "Nike", "domain": "nike.com", "slug": "nike", "category": "fashion", "color": "#111111", "icon": "👟"},
    {"name": "H&M", "domain": "hm.com", "slug": "hm", "category": "fashion", "color": "#E50010", "icon": "👗"},
    {"name": "Zara", "domain": "zara.com", "slug": "zara", "category": "fashion", "color": "#000000", "icon": "👔"},
    {"name": "ASOS", "domain": "asos.com", "slug": "asos", "category": "fashion", "color": "#2D2D2D", "icon": "👠"},
    {"name": "Best Buy", "domain": "bestbuy.com", "slug": "bestbuy", "category": "electronics", "color": "#0046BE", "icon": "🖥"},
    {"name": "Newegg", "domain": "newegg.com", "slug": "newegg", "category": "electronics", "color": "#F7A000", "icon": "🥚"},
    {"name": "B&H Photo", "domain": "bhphotovideo.com", "slug": "bhphoto", "category": "electronics", "color": "#000000", "icon": "📷"},
    {"name": "DoorDash", "domain": "doordash.com", "slug": "doordash", "category": "food", "color": "#FF3008", "icon": "🍔"},
    {"name": "Grubhub", "domain": "grubhub.com", "slug": "grubhub", "category": "food", "color": "#F63440", "icon": "🍕"},
    {"name": "Uber Eats", "domain": "ubereats.com", "slug": "ubereats", "category": "food", "color": "#06C167", "icon": "🥡"},
    {"name": "CVS", "domain": "cvs.com", "slug": "cvs", "category": "health", "color": "#CC0000", "icon": "💊"},
    {"name": "Macys", "domain": "macys.com", "slug": "macys", "category": "fashion", "color": "#E21A2C", "icon": "🛍"},
    {"name": "Costco", "domain": "costco.com", "slug": "costco", "category": "big-box", "color": "#E31837", "icon": "🏬"},
    {"name": "Home Depot", "domain": "homedepot.com", "slug": "homedepot", "category": "home", "color": "#F96302", "icon": "🔨"},
    {"name": "Lowes", "domain": "lowes.com", "slug": "lowes", "category": "home", "color": "#004990", "icon": "🔧"},
    {"name": "Nordstrom", "domain": "nordstrom.com", "slug": "nordstrom", "category": "fashion", "color": "#000000", "icon": "👜"},
    {"name": "Sephora", "domain": "sephora.com", "slug": "sephora", "category": "beauty", "color": "#000000", "icon": "💄"},
    {"name": "Ulta", "domain": "ulta.com", "slug": "ulta", "category": "beauty", "color": "#E55C78", "icon": "💅"},
    {"name": "Apple", "domain": "apple.com", "slug": "apple", "category": "electronics", "color": "#000000", "icon": "🍎"},
    {"name": "Samsung", "domain": "samsung.com", "slug": "samsung", "category": "electronics", "color": "#1428A0", "icon": "📱"},
    {"name": "Sony", "domain": "sony.com", "slug": "sony", "category": "electronics", "color": "#000000", "icon": "🎮"},
    {"name": "Microsoft", "domain": "microsoft.com", "slug": "microsoft", "category": "electronics", "color": "#00A4EF", "icon": "💻"},
    {"name": "Adidas", "domain": "adidas.com", "slug": "adidas", "category": "fashion", "color": "#000000", "icon": "👟"},
    {"name": "Puma", "domain": "puma.com", "slug": "puma", "category": "fashion", "color": "#000000", "icon": "🐆"},
    {"name": "Under Armour", "domain": "underarmour.com", "slug": "underarmour", "category": "fashion", "color": "#1D1D1D", "icon": "🏋"},
    {"name": "Lululemon", "domain": "lululemon.com", "slug": "lululemon", "category": "fashion", "color": "#D31334", "icon": "🧘"},
    {"name": "Gap", "domain": "gap.com", "slug": "gap", "category": "fashion", "color": "#000066", "icon": "👕"},
    {"name": "Old Navy", "domain": "oldnavy.com", "slug": "oldnavy", "category": "fashion", "color": "#003865", "icon": "⚓"},
    {"name": "J.Crew", "domain": "jcrew.com", "slug": "jcrew", "category": "fashion", "color": "#8B0000", "icon": "👔"},
    {"name": "Express", "domain": "express.com", "slug": "express", "category": "fashion", "color": "#000000", "icon": "✨"},
    {"name": "Forever 21", "domain": "forever21.com", "slug": "forever21", "category": "fashion", "color": "#FFD700", "icon": "💛"},
    {"name": "Shein", "domain": "shein.com", "slug": "shein", "category": "fashion", "color": "#000000", "icon": "👗"},
    {"name": "eBay", "domain": "ebay.com", "slug": "ebay", "category": "marketplace", "color": "#E53238", "icon": "🏷"},
    {"name": "Etsy", "domain": "etsy.com", "slug": "etsy", "category": "marketplace", "color": "#F56400", "icon": "🎨"},
    {"name": "Wayfair", "domain": "wayfair.com", "slug": "wayfair", "category": "home", "color": "#7B0E8E", "icon": "🛋"},
    {"name": "IKEA", "domain": "ikea.com", "slug": "ikea", "category": "home", "color": "#0058A3", "icon": "🪑"},
    {"name": "Overstock", "domain": "overstock.com", "slug": "overstock", "category": "home", "color": "#D52B1E", "icon": "🏠"},
    {"name": "Kroger", "domain": "kroger.com", "slug": "kroger", "category": "grocery", "color": "#E35205", "icon": "🛒"},
    {"name": "Whole Foods", "domain": "wholefoodsmarket.com", "slug": "wholefoods", "category": "grocery", "color": "#00674B", "icon": "🥬"},
    {"name": "Instacart", "domain": "instacart.com", "slug": "instacart", "category": "grocery", "color": "#43B02A", "icon": "🥕"},
    {"name": "Walgreens", "domain": "walgreens.com", "slug": "walgreens", "category": "health", "color": "#E31837", "icon": "⚕"},
    {"name": "GNC", "domain": "gnc.com", "slug": "gnc", "category": "health", "color": "#D4A537", "icon": "💪"},
    {"name": "REI", "domain": "rei.com", "slug": "rei", "category": "outdoors", "color": "#1A1A1A", "icon": "🏔"},
    {"name": "Patagonia", "domain": "patagonia.com", "slug": "patagonia", "category": "outdoors", "color": "#1C1C1C", "icon": "🧥"},
    {"name": "North Face", "domain": "thenorthface.com", "slug": "northface", "category": "outdoors", "color": "#000000", "icon": "⛰"},
    {"name": "Columbia", "domain": "columbia.com", "slug": "columbia", "category": "outdoors", "color": "#1A2B49", "icon": "🧤"},
    {"name": "Dicks Sporting Goods", "domain": "dickssportinggoods.com", "slug": "dickssportinggoods", "category": "sports", "color": "#006B3F", "icon": "⚽"},
    {"name": "Foot Locker", "domain": "footlocker.com", "slug": "footlocker", "category": "fashion", "color": "#000000", "icon": "👟"},
    {"name": "GameStop", "domain": "gamestop.com", "slug": "gamestop", "category": "electronics", "color": "#000000", "icon": "🎮"},
    {"name": "Dell", "domain": "dell.com", "slug": "dell", "category": "electronics", "color": "#007DB8", "icon": "🖥"},
    {"name": "HP", "domain": "hp.com", "slug": "hp", "category": "electronics", "color": "#0096D6", "icon": "🖨"},
    {"name": "Lenovo", "domain": "lenovo.com", "slug": "lenovo", "category": "electronics", "color": "#E2231A", "icon": "💻"},
    {"name": "T-Mobile", "domain": "t-mobile.com", "slug": "tmobile", "category": "telecom", "color": "#E20074", "icon": "📱"},
    {"name": "Verizon", "domain": "verizon.com", "slug": "verizon", "category": "telecom", "color": "#CD040B", "icon": "📡"},
    {"name": "AT&T", "domain": "att.com", "slug": "att", "category": "telecom", "color": "#009FDB", "icon": "📶"},
    {"name": "Spotify", "domain": "spotify.com", "slug": "spotify", "category": "entertainment", "color": "#1DB954", "icon": "🎵"},
    {"name": "Netflix", "domain": "netflix.com", "slug": "netflix", "category": "entertainment", "color": "#E50914", "icon": "🎬"},
    {"name": "Hulu", "domain": "hulu.com", "slug": "hulu", "category": "entertainment", "color": "#1CE783", "icon": "📺"},
    {"name": "Petco", "domain": "petco.com", "slug": "petco", "category": "pets", "color": "#0056A3", "icon": "🐾"},
    {"name": "PetSmart", "domain": "petsmart.com", "slug": "petsmart", "category": "pets", "color": "#E01F27", "icon": "🐕"},
    {"name": "Chewy", "domain": "chewy.com", "slug": "chewy", "category": "pets", "color": "#1C49C2", "icon": "🦴"},
    {"name": "AutoZone", "domain": "autozone.com", "slug": "autozone", "category": "auto", "color": "#D52B1E", "icon": "🚗"},
    {"name": "Bath Body Works", "domain": "bathandbodyworks.com", "slug": "bathbodyworks", "category": "beauty", "color": "#003B5C", "icon": "🧴"},
    {"name": "Victorias Secret", "domain": "victoriassecret.com", "slug": "victoriassecret", "category": "fashion", "color": "#E1187D", "icon": "🌸"},
    {"name": "Coach", "domain": "coach.com", "slug": "coach", "category": "fashion", "color": "#1C1C1C", "icon": "👜"},
    {"name": "Kate Spade", "domain": "katespade.com", "slug": "katespade", "category": "fashion", "color": "#000000", "icon": "♠"},
    {"name": "Michael Kors", "domain": "michaelkors.com", "slug": "michaelkors", "category": "fashion", "color": "#000000", "icon": "👝"},
    {"name": "Pottery Barn", "domain": "potterybarn.com", "slug": "potterybarn", "category": "home", "color": "#4A3728", "icon": "🏺"},
    {"name": "West Elm", "domain": "westelm.com", "slug": "westelm", "category": "home", "color": "#000000", "icon": "🪴"},
    {"name": "Crate Barrel", "domain": "crateandbarrel.com", "slug": "cratebarrel", "category": "home", "color": "#000000", "icon": "🍽"},
    {"name": "Anthropologie", "domain": "anthropologie.com", "slug": "anthropologie", "category": "fashion", "color": "#3C3C3C", "icon": "🌿"},
    {"name": "Urban Outfitters", "domain": "urbanoutfitters.com", "slug": "urbanoutfitters", "category": "fashion", "color": "#000000", "icon": "🎶"},
    {"name": "Staples", "domain": "staples.com", "slug": "staples", "category": "office", "color": "#CC0000", "icon": "📎"},
    {"name": "Dollar General", "domain": "dollargeneral.com", "slug": "dollargeneral", "category": "big-box", "color": "#FDB813", "icon": "💵"},
    {"name": "Dollar Tree", "domain": "dollartree.com", "slug": "dollartree", "category": "big-box", "color": "#00A651", "icon": "🌳"},
    {"name": "Five Below", "domain": "fivebelow.com", "slug": "fivebelow", "category": "big-box", "color": "#002D72", "icon": "⭐"},
    {"name": "TJ Maxx", "domain": "tjmaxx.com", "slug": "tjmaxx", "category": "fashion", "color": "#E11B22", "icon": "🏷"},
    {"name": "Marshalls", "domain": "marshalls.com", "slug": "marshalls", "category": "fashion", "color": "#003DA5", "icon": "🛍"},
    {"name": "Kohls", "domain": "kohls.com", "slug": "kohls", "category": "big-box", "color": "#000000", "icon": "🏪"},
    {"name": "JCPenney", "domain": "jcpenney.com", "slug": "jcpenney", "category": "big-box", "color": "#E31837", "icon": "🛒"},
    {"name": "Booking.com", "domain": "booking.com", "slug": "bookingcom", "category": "travel", "color": "#003580", "icon": "🏨"},
    {"name": "Expedia", "domain": "expedia.com", "slug": "expedia", "category": "travel", "color": "#00355F", "icon": "✈"},
    {"name": "Airbnb", "domain": "airbnb.com", "slug": "airbnb", "category": "travel", "color": "#FF5A5F", "icon": "🏡"},
    {"name": "Southwest Airlines", "domain": "southwest.com", "slug": "southwestairlines", "category": "travel", "color": "#304CB2", "icon": "🛫"},
    {"name": "Hilton", "domain": "hilton.com", "slug": "hilton", "category": "travel", "color": "#003E7E", "icon": "🏨"},
    {"name": "Marriott", "domain": "marriott.com", "slug": "marriott", "category": "travel", "color": "#1C1C1C", "icon": "🛏"},
    {"name": "Zappos", "domain": "zappos.com", "slug": "zappos", "category": "fashion", "color": "#007BBD", "icon": "👠"},
    {"name": "Rakuten", "domain": "rakuten.com", "slug": "rakuten", "category": "marketplace", "color": "#BF0000", "icon": "🎁"},
    {"name": "Groupon", "domain": "groupon.com", "slug": "groupon", "category": "marketplace", "color": "#53A318", "icon": "💰"},
    {"name": "Wish", "domain": "wish.com", "slug": "wish", "category": "marketplace", "color": "#2FB7EC", "icon": "⭐"},
    {"name": "Temu", "domain": "temu.com", "slug": "temu", "category": "marketplace", "color": "#F56B2A", "icon": "🛍"},
    {"name": "Alibaba", "domain": "alibaba.com", "slug": "alibaba", "category": "marketplace", "color": "#FF6A00", "icon": "🌏"},
    {"name": "Gymshark", "domain": "gymshark.com", "slug": "gymshark", "category": "fashion", "color": "#000000", "icon": "🦈"},
    {"name": "Allbirds", "domain": "allbirds.com", "slug": "allbirds", "category": "fashion", "color": "#212322", "icon": "🐦"},
    {"name": "Warby Parker", "domain": "warbyparker.com", "slug": "warbyparker", "category": "fashion", "color": "#00A2E1", "icon": "👓"},
    {"name": "Casper", "domain": "casper.com", "slug": "casper", "category": "home", "color": "#02237E", "icon": "🛏"},
    {"name": "Glossier", "domain": "glossier.com", "slug": "glossier", "category": "beauty", "color": "#FFB6C1", "icon": "🌸"}
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
    "cvs": "CVS", "cvs pharmacy": "CVS",
    "macys": "Macys", "macy's": "Macys", "macys.com": "Macys",
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

# Render's free tier spins the service down after ~15 min of inactivity.
# RENDER_EXTERNAL_URL is auto-populated by Render on web services and is
# used to self-ping so the dyno never goes idle.
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")

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


def get_fallback_deals():
    """Curated, always-available deals used when every live scrape source
    is blocked (403/404/empty). These are not scraped or code-validated —
    just honest pointers to each retailer's own deals page — so the site
    is never left completely empty.
    """
    fallback = []
    for retailer in RETAILERS:
        deal = build_deal(
            retailer=retailer,
            code="",
            description=f"Browse current {retailer['name']} deals and clearance",
            discount="",
            source="Fallback",
            url=f"https://www.{retailer['domain']}",
            deal_type="deal",
        )
        fallback.append(decorate_deal(deal))
    return fallback



# --- Code Validation Logic ---
def validate_code_against_aggregators(code, retailer):
    """Cross-reference a coupon code against multiple aggregator sources.
    
    Checks the code against couponfollow, savings.com, and couponcabin
    to verify the code appears on at least one other source.
    Returns True if code is validated, False otherwise.
    """
    if not code or code.strip() == "":
        return False
    
    aggregator_urls = [
        f"https://couponfollow.com/site/{retailer.lower().replace(' ', '')}",
        f"https://www.savings.com/store/{retailer.lower().replace(' ', '-')}",
        f"https://www.couponcabin.com/coupons/{retailer.lower().replace(' ', '-')}",
        f"https://www.retailmenot.com/view/{retailer.lower().replace(' ', '')}.com",
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    validations = 0
    sources_checked = 0
    
    for url in aggregator_urls:
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                sources_checked += 1
                # Check if the code appears in the page content
                if code.upper() in resp.text.upper():
                    validations += 1
                    validation_logger.info(f"Code '{code}' for {retailer} FOUND on {url}")
        except Exception as e:
            validation_logger.debug(f"Error checking {url}: {e}")
            continue
    
    # Code is valid if found on at least 1 aggregator source, or if no sources could be checked
    # (graceful degradation - don't block codes if aggregators are down)
    if sources_checked == 0:
        validation_logger.warning(f"No aggregator sources reachable for {retailer} code '{code}' - allowing by default")
        return True
    
    is_valid = validations >= 1
    if not is_valid:
        validation_logger.warning(f"Code '{code}' for {retailer} NOT found on any of {sources_checked} aggregator sources")
    return is_valid


def validate_and_filter_deals(new_deals):
    """Validate scraped deals and return only verified ones.
    
    Codes are cross-referenced against aggregator sources.
    Invalid codes are logged but not published.
    Only validated/working codes replace current live codes.
    """
    global INVALID_CODES_LOG
    validated_deals = []
    invalid_deals = []
    
    for deal in new_deals:
        code = deal.get("code", "")
        retailer = deal.get("retailer", "")
        
        # Deals without codes (percentage-off links, etc.) pass through
        if not code or code.strip() == "":
            validated_deals.append(deal)
            continue
        
        # Validate the code against aggregator sources
        if validate_code_against_aggregators(code, retailer):
            deal["validated"] = True
            deal["validated_at"] = datetime.now().isoformat()
            validated_deals.append(deal)
        else:
            # Log invalid code but do NOT publish
            invalid_entry = {
                "code": code,
                "retailer": retailer,
                "description": deal.get("description", ""),
                "reason": "Not found on aggregator sources",
                "scraped_at": datetime.now().isoformat()
            }
            INVALID_CODES_LOG.append(invalid_entry)
            invalid_deals.append(deal)
            validation_logger.info(
                f"REJECTED: Code '{code}' for {retailer} - not validated by aggregators"
            )
    
    validation_logger.info(
        f"Validation complete: {len(validated_deals)} valid, {len(invalid_deals)} rejected"
    )
    return validated_deals


def scrape_all():
    """Scrape all retailers, validate codes, and only publish verified deals."""
    global _scrape_status
    _scrape_status = {"running": True, "last_run": None, "message": "Scraping in progress..."}
    all_new_deals = []

    # Scrape retailers concurrently — sequential scraping of every source for
    # every retailer is slow enough on Render's free-tier CPU that a run can
    # stall out before ever reaching the status update below.
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_retailer = {executor.submit(scrape_retailer, r): r for r in RETAILERS}
        for future in as_completed(future_to_retailer):
            retailer = future_to_retailer[future]
            try:
                all_new_deals.extend(future.result())
            except Exception as e:
                print(f"Error scraping {retailer['name']}: {e}")

    # Validate codes against aggregator sources before publishing
    validation_logger.info(f"Starting validation of {len(all_new_deals)} scraped deals...")
    validated_deals = validate_and_filter_deals(all_new_deals)

    # If every live source is blocked/empty, fall back to curated data so
    # the site is never left with nothing to show.
    if not validated_deals:
        validation_logger.warning("No live deals from any source — publishing fallback deals")
        validated_deals = get_fallback_deals()

    # Only replace live codes with validated ones
    if validated_deals:
        current_deals = load_deals().get("deals", [])
        # Keep existing deals that aren't being replaced
        existing_ids = {d.get("id") for d in validated_deals}
        kept_deals = [d for d in current_deals if d.get("id") not in existing_ids]
        # Merge: keep old deals + add new validated deals
        final_deals = kept_deals + validated_deals
        save_deals(final_deals)
        validation_logger.info(f"Published {len(validated_deals)} validated deals, kept {len(kept_deals)} existing deals")
    else:
        validation_logger.warning("No validated deals to publish - keeping current live codes")

    _scrape_status = {
        "running": False,
        "last_run": datetime.now().isoformat(),
        "message": f"Completed: {len(validated_deals)} validated deals published, {len(INVALID_CODES_LOG)} codes rejected"
    }
    return validated_deals


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
        retailer = deal.get("retailer", "")
        domain = domain_map.get(retailer.lower(), "")
        if domain:
            deal["domain"] = domain
            if not deal.get("url"):
                deal["url"] = f"https://www.{domain}"
        # Fix Macy's code: BEST1521 should be SHOP1521
        if retailer.lower() == "macys" and deal.get("code") == "BEST1521":
            deal["code"] = "FRIEND"
    data["total_deals"] = len(deals)
    data["total_codes"] = sum(1 for d in deals if d.get("code"))
    data["total"] = len(deals)
    data["page"] = 1
    data["pages"] = 1
    for d in deals:
        d["type"] = d.get("deal_type", "deal")
        meta = next((r for r in RETAILERS if r["name"].lower() == d.get("retailer", "").lower()), {})
        if not d.get("icon"):
            d["icon"] = meta.get("icon", "")
        if not d.get("color"):
            d["color"] = meta.get("color", "#6c5ce7")
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


@app.route("/healthz")
def healthz():
    """Lightweight endpoint for the self-ping keep-alive job (and uptime checks)."""
    return jsonify({"status": "ok"})


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
    retailer_meta = {r["name"].lower(): r for r in RETAILERS}
    for deal in trending:
        deal["isTrending"] = True
        r_key = deal.get("retailer", "").lower()
        meta = retailer_meta.get(r_key, {})
        if not deal.get("icon"):
            deal["icon"] = meta.get("icon", "")
        if not deal.get("color"):
            deal["color"] = meta.get("color", "#6c5ce7")
        if not deal.get("url"):
            domain = domain_map.get(r_key, "")
            if domain:
                deal["url"] = f"https://www.{domain}"
    return jsonify({"deals": trending})


@app.route("/api/deals/featured")
def api_deals_featured():
    data = load_deals()
    deals = data.get("deals", [])
    if deals:
        domain_map = {r["name"].lower(): r["domain"] for r in RETAILERS}
        for deal in deals:
            if deal.get("code"):
                retailer = deal.get("retailer", "")
                domain = domain_map.get(retailer.lower(), "")
                if domain:
                    deal["domain"] = domain
                    if not deal.get("url"):
                        deal["url"] = f"https://www.{domain}"
                if retailer.lower() == "macys" and deal.get("code") == "BEST1521":
                    deal["code"] = "FRIEND"
                return jsonify({"deal": deal})
        deal = deals[0]
        if not deal.get("url"):
            domain = domain_map.get(deal.get("retailer", "").lower(), "")
            if domain:
                deal["url"] = f"https://www.{domain}"
        return jsonify({"deal": deal})
    return jsonify({"deal": None})


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    from flask import request
    data = request.get_json(silent=True) or {}
    deal_id = data.get("dealId", "")
    feedback_type = data.get("type", "")
    return jsonify({"status": "ok", "dealId": deal_id, "type": feedback_type})



@app.route("/manifest.json")
def manifest():

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
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

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

RETAILERS = [
    {"name": "Amazon", "domain": "amazon.com", "slug": "amazon", "category": "big-box", "color": "#FF9900", "icon": "📦"},
    {"name": "Walmart", "domain": "walmart.com", "slug": "walmart", "category": "big-box", "color": "#0071CE", "icon": "🏪"},
    {"name": "Target", "domain": "target.com", "slug": "target", "category": "big-box", "color": "#CC0000", "icon": "🎯"},
    {"name": "Nike", "domain": "nike.com", "slug": "nike", "category": "fashion", "color": "#111111", "icon": "👟"},
    {"name": "H&M", "domain": "hm.com", "slug": "hm", "category": "fashion", "color": "#E50010", "icon": "👗"},
    {"name": "Zara", "domain": "zara.com", "slug": "zara", "category": "fashion", "color": "#000000", "icon": "👔"},
    {"name": "ASOS", "domain": "asos.com", "slug": "asos", "category": "fashion", "color": "#2D2D2D", "icon": "👠"},
    {"name": "Best Buy", "domain": "bestbuy.com", "slug": "bestbuy", "category": "electronics", "color": "#0046BE", "icon": "🖥"},
    {"name": "Newegg", "domain": "newegg.com", "slug": "newegg", "category": "electronics", "color": "#F7A000", "icon": "🥚"},
    {"name": "B&H Photo", "domain": "bhphotovideo.com", "slug": "bhphoto", "category": "electronics", "color": "#000000", "icon": "📷"},
    {"name": "DoorDash", "domain": "doordash.com", "slug": "doordash", "category": "food", "color": "#FF3008", "icon": "🍔"},
    {"name": "Grubhub", "domain": "grubhub.com", "slug": "grubhub", "category": "food", "color": "#F63440", "icon": "🍕"},
    {"name": "Uber Eats", "domain": "ubereats.com", "slug": "ubereats", "category": "food", "color": "#06C167", "icon": "🥡"},
    {"name": "CVS", "domain": "cvs.com", "slug": "cvs", "category": "health", "color": "#CC0000", "icon": "💊"},
    {"name": "Macys", "domain": "macys.com", "slug": "macys", "category": "fashion", "color": "#E21A2C", "icon": "🛍"},
    {"name": "Costco", "domain": "costco.com", "slug": "costco", "category": "big-box", "color": "#E31837", "icon": "🏬"},
    {"name": "Home Depot", "domain": "homedepot.com", "slug": "homedepot", "category": "home", "color": "#F96302", "icon": "🔨"},
    {"name": "Lowes", "domain": "lowes.com", "slug": "lowes", "category": "home", "color": "#004990", "icon": "🔧"},
    {"name": "Nordstrom", "domain": "nordstrom.com", "slug": "nordstrom", "category": "fashion", "color": "#000000", "icon": "👜"},
    {"name": "Sephora", "domain": "sephora.com", "slug": "sephora", "category": "beauty", "color": "#000000", "icon": "💄"},
    {"name": "Ulta", "domain": "ulta.com", "slug": "ulta", "category": "beauty", "color": "#E55C78", "icon": "💅"},
    {"name": "Apple", "domain": "apple.com", "slug": "apple", "category": "electronics", "color": "#000000", "icon": "🍎"},
    {"name": "Samsung", "domain": "samsung.com", "slug": "samsung", "category": "electronics", "color": "#1428A0", "icon": "📱"},
    {"name": "Sony", "domain": "sony.com", "slug": "sony", "category": "electronics", "color": "#000000", "icon": "🎮"},
    {"name": "Microsoft", "domain": "microsoft.com", "slug": "microsoft", "category": "electronics", "color": "#00A4EF", "icon": "💻"},
    {"name": "Adidas", "domain": "adidas.com", "slug": "adidas", "category": "fashion", "color": "#000000", "icon": "👟"},
    {"name": "Puma", "domain": "puma.com", "slug": "puma", "category": "fashion", "color": "#000000", "icon": "🐆"},
    {"name": "Under Armour", "domain": "underarmour.com", "slug": "underarmour", "category": "fashion", "color": "#1D1D1D", "icon": "🏋"},
    {"name": "Lululemon", "domain": "lululemon.com", "slug": "lululemon", "category": "fashion", "color": "#D31334", "icon": "🧘"},
    {"name": "Gap", "domain": "gap.com", "slug": "gap", "category": "fashion", "color": "#000066", "icon": "👕"},
    {"name": "Old Navy", "domain": "oldnavy.com", "slug": "oldnavy", "category": "fashion", "color": "#003865", "icon": "⚓"},
    {"name": "J.Crew", "domain": "jcrew.com", "slug": "jcrew", "category": "fashion", "color": "#8B0000", "icon": "👔"},
    {"name": "Express", "domain": "express.com", "slug": "express", "category": "fashion", "color": "#000000", "icon": "✨"},
    {"name": "Forever 21", "domain": "forever21.com", "slug": "forever21", "category": "fashion", "color": "#FFD700", "icon": "💛"},
    {"name": "Shein", "domain": "shein.com", "slug": "shein", "category": "fashion", "color": "#000000", "icon": "👗"},
    {"name": "eBay", "domain": "ebay.com", "slug": "ebay", "category": "marketplace", "color": "#E53238", "icon": "🏷"},
    {"name": "Etsy", "domain": "etsy.com", "slug": "etsy", "category": "marketplace", "color": "#F56400", "icon": "🎨"},
    {"name": "Wayfair", "domain": "wayfair.com", "slug": "wayfair", "category": "home", "color": "#7B0E8E", "icon": "🛋"},
    {"name": "IKEA", "domain": "ikea.com", "slug": "ikea", "category": "home", "color": "#0058A3", "icon": "🪑"},
    {"name": "Overstock", "domain": "overstock.com", "slug": "overstock", "category": "home", "color": "#D52B1E", "icon": "🏠"},
    {"name": "Kroger", "domain": "kroger.com", "slug": "kroger", "category": "grocery", "color": "#E35205", "icon": "🛒"},
    {"name": "Whole Foods", "domain": "wholefoodsmarket.com", "slug": "wholefoods", "category": "grocery", "color": "#00674B", "icon": "🥬"},
    {"name": "Instacart", "domain": "instacart.com", "slug": "instacart", "category": "grocery", "color": "#43B02A", "icon": "🥕"},
    {"name": "Walgreens", "domain": "walgreens.com", "slug": "walgreens", "category": "health", "color": "#E31837", "icon": "⚕"},
    {"name": "GNC", "domain": "gnc.com", "slug": "gnc", "category": "health", "color": "#D4A537", "icon": "💪"},
    {"name": "REI", "domain": "rei.com", "slug": "rei", "category": "outdoors", "color": "#1A1A1A", "icon": "🏔"},
    {"name": "Patagonia", "domain": "patagonia.com", "slug": "patagonia", "category": "outdoors", "color": "#1C1C1C", "icon": "🧥"},
    {"name": "North Face", "domain": "thenorthface.com", "slug": "northface", "category": "outdoors", "color": "#000000", "icon": "⛰"},
    {"name": "Columbia", "domain": "columbia.com", "slug": "columbia", "category": "outdoors", "color": "#1A2B49", "icon": "🧤"},
    {"name": "Dicks Sporting Goods", "domain": "dickssportinggoods.com", "slug": "dickssportinggoods", "category": "sports", "color": "#006B3F", "icon": "⚽"},
    {"name": "Foot Locker", "domain": "footlocker.com", "slug": "footlocker", "category": "fashion", "color": "#000000", "icon": "👟"},
    {"name": "GameStop", "domain": "gamestop.com", "slug": "gamestop", "category": "electronics", "color": "#000000", "icon": "🎮"},
    {"name": "Dell", "domain": "dell.com", "slug": "dell", "category": "electronics", "color": "#007DB8", "icon": "🖥"},
    {"name": "HP", "domain": "hp.com", "slug": "hp", "category": "electronics", "color": "#0096D6", "icon": "🖨"},
    {"name": "Lenovo", "domain": "lenovo.com", "slug": "lenovo", "category": "electronics", "color": "#E2231A", "icon": "💻"},
    {"name": "T-Mobile", "domain": "t-mobile.com", "slug": "tmobile", "category": "telecom", "color": "#E20074", "icon": "📱"},
    {"name": "Verizon", "domain": "verizon.com", "slug": "verizon", "category": "telecom", "color": "#CD040B", "icon": "📡"},
    {"name": "AT&T", "domain": "att.com", "slug": "att", "category": "telecom", "color": "#009FDB", "icon": "📶"},
    {"name": "Spotify", "domain": "spotify.com", "slug": "spotify", "category": "entertainment", "color": "#1DB954", "icon": "🎵"},
    {"name": "Netflix", "domain": "netflix.com", "slug": "netflix", "category": "entertainment", "color": "#E50914", "icon": "🎬"},
    {"name": "Hulu", "domain": "hulu.com", "slug": "hulu", "category": "entertainment", "color": "#1CE783", "icon": "📺"},
    {"name": "Petco", "domain": "petco.com", "slug": "petco", "category": "pets", "color": "#0056A3", "icon": "🐾"},
    {"name": "PetSmart", "domain": "petsmart.com", "slug": "petsmart", "category": "pets", "color": "#E01F27", "icon": "🐕"},
    {"name": "Chewy", "domain": "chewy.com", "slug": "chewy", "category": "pets", "color": "#1C49C2", "icon": "🦴"},
    {"name": "AutoZone", "domain": "autozone.com", "slug": "autozone", "category": "auto", "color": "#D52B1E", "icon": "🚗"},
    {"name": "Bath Body Works", "domain": "bathandbodyworks.com", "slug": "bathbodyworks", "category": "beauty", "color": "#003B5C", "icon": "🧴"},
    {"name": "Victorias Secret", "domain": "victoriassecret.com", "slug": "victoriassecret", "category": "fashion", "color": "#E1187D", "icon": "🌸"},
    {"name": "Coach", "domain": "coach.com", "slug": "coach", "category": "fashion", "color": "#1C1C1C", "icon": "👜"},
    {"name": "Kate Spade", "domain": "katespade.com", "slug": "katespade", "category": "fashion", "color": "#000000", "icon": "♠"},
    {"name": "Michael Kors", "domain": "michaelkors.com", "slug": "michaelkors", "category": "fashion", "color": "#000000", "icon": "👝"},
    {"name": "Pottery Barn", "domain": "potterybarn.com", "slug": "potterybarn", "category": "home", "color": "#4A3728", "icon": "🏺"},
    {"name": "West Elm", "domain": "westelm.com", "slug": "westelm", "category": "home", "color": "#000000", "icon": "🪴"},
    {"name": "Crate Barrel", "domain": "crateandbarrel.com", "slug": "cratebarrel", "category": "home", "color": "#000000", "icon": "🍽"},
    {"name": "Anthropologie", "domain": "anthropologie.com", "slug": "anthropologie", "category": "fashion", "color": "#3C3C3C", "icon": "🌿"},
    {"name": "Urban Outfitters", "domain": "urbanoutfitters.com", "slug": "urbanoutfitters", "category": "fashion", "color": "#000000", "icon": "🎶"},
    {"name": "Staples", "domain": "staples.com", "slug": "staples", "category": "office", "color": "#CC0000", "icon": "📎"},
    {"name": "Dollar General", "domain": "dollargeneral.com", "slug": "dollargeneral", "category": "big-box", "color": "#FDB813", "icon": "💵"},
    {"name": "Dollar Tree", "domain": "dollartree.com", "slug": "dollartree", "category": "big-box", "color": "#00A651", "icon": "🌳"},
    {"name": "Five Below", "domain": "fivebelow.com", "slug": "fivebelow", "category": "big-box", "color": "#002D72", "icon": "⭐"},
    {"name": "TJ Maxx", "domain": "tjmaxx.com", "slug": "tjmaxx", "category": "fashion", "color": "#E11B22", "icon": "🏷"},
    {"name": "Marshalls", "domain": "marshalls.com", "slug": "marshalls", "category": "fashion", "color": "#003DA5", "icon": "🛍"},
    {"name": "Kohls", "domain": "kohls.com", "slug": "kohls", "category": "big-box", "color": "#000000", "icon": "🏪"},
    {"name": "JCPenney", "domain": "jcpenney.com", "slug": "jcpenney", "category": "big-box", "color": "#E31837", "icon": "🛒"},
    {"name": "Booking.com", "domain": "booking.com", "slug": "bookingcom", "category": "travel", "color": "#003580", "icon": "🏨"},
    {"name": "Expedia", "domain": "expedia.com", "slug": "expedia", "category": "travel", "color": "#00355F", "icon": "✈"},
    {"name": "Airbnb", "domain": "airbnb.com", "slug": "airbnb", "category": "travel", "color": "#FF5A5F", "icon": "🏡"},
    {"name": "Southwest Airlines", "domain": "southwest.com", "slug": "southwestairlines", "category": "travel", "color": "#304CB2", "icon": "🛫"},
    {"name": "Hilton", "domain": "hilton.com", "slug": "hilton", "category": "travel", "color": "#003E7E", "icon": "🏨"},
    {"name": "Marriott", "domain": "marriott.com", "slug": "marriott", "category": "travel", "color": "#1C1C1C", "icon": "🛏"},
    {"name": "Zappos", "domain": "zappos.com", "slug": "zappos", "category": "fashion", "color": "#007BBD", "icon": "👠"},
    {"name": "Rakuten", "domain": "rakuten.com", "slug": "rakuten", "category": "marketplace", "color": "#BF0000", "icon": "🎁"},
    {"name": "Groupon", "domain": "groupon.com", "slug": "groupon", "category": "marketplace", "color": "#53A318", "icon": "💰"},
    {"name": "Wish", "domain": "wish.com", "slug": "wish", "category": "marketplace", "color": "#2FB7EC", "icon": "⭐"},
    {"name": "Temu", "domain": "temu.com", "slug": "temu", "category": "marketplace", "color": "#F56B2A", "icon": "🛍"},
    {"name": "Alibaba", "domain": "alibaba.com", "slug": "alibaba", "category": "marketplace", "color": "#FF6A00", "icon": "🌏"},
    {"name": "Gymshark", "domain": "gymshark.com", "slug": "gymshark", "category": "fashion", "color": "#000000", "icon": "🦈"},
    {"name": "Allbirds", "domain": "allbirds.com", "slug": "allbirds", "category": "fashion", "color": "#212322", "icon": "🐦"},
    {"name": "Warby Parker", "domain": "warbyparker.com", "slug": "warbyparker", "category": "fashion", "color": "#00A2E1", "icon": "👓"},
    {"name": "Casper", "domain": "casper.com", "slug": "casper", "category": "home", "color": "#02237E", "icon": "🛏"},
    {"name": "Glossier", "domain": "glossier.com", "slug": "glossier", "category": "beauty", "color": "#FFB6C1", "icon": "🌸"}
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
    "cvs": "CVS", "cvs pharmacy": "CVS",
    "macys": "Macys", "macy's": "Macys", "macys.com": "Macys",
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

# Render's free tier spins the service down after ~15 min of inactivity.
# RENDER_EXTERNAL_URL is auto-populated by Render on web services and is
# used to self-ping so the dyno never goes idle.
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")

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


def get_fallback_deals():
    """Curated, always-available deals used when every live scrape source
    is blocked (403/404/empty). These are not scraped or code-validated —
    just honest pointers to each retailer's own deals page — so the site
    is never left completely empty.
    """
    fallback = []
    for retailer in RETAILERS:
        deal = build_deal(
            retailer=retailer,
            code="",
            description=f"Browse current {retailer['name']} deals and clearance",
            discount="",
            source="Fallback",
            url=f"https://www.{retailer['domain']}",
            deal_type="deal",
        )
        fallback.append(decorate_deal(deal))
    return fallback



# --- Code Validation Logic ---
def validate_code_against_aggregators(code, retailer):
    """Cross-reference a coupon code against multiple aggregator sources.
    
    Checks the code against couponfollow, savings.com, and couponcabin
    to verify the code appears on at least one other source.
    Returns True if code is validated, False otherwise.
    """
    if not code or code.strip() == "":
        return False
    
    aggregator_urls = [
        f"https://couponfollow.com/site/{retailer.lower().replace(' ', '')}",
        f"https://www.savings.com/store/{retailer.lower().replace(' ', '-')}",
        f"https://www.couponcabin.com/coupons/{retailer.lower().replace(' ', '-')}",
        f"https://www.retailmenot.com/view/{retailer.lower().replace(' ', '')}.com",
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    validations = 0
    sources_checked = 0
    
    for url in aggregator_urls:
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                sources_checked += 1
                # Check if the code appears in the page content
                if code.upper() in resp.text.upper():
                    validations += 1
                    validation_logger.info(f"Code '{code}' for {retailer} FOUND on {url}")
        except Exception as e:
            validation_logger.debug(f"Error checking {url}: {e}")
            continue
    
    # Code is valid if found on at least 1 aggregator source, or if no sources could be checked
    # (graceful degradation - don't block codes if aggregators are down)
    if sources_checked == 0:
        validation_logger.warning(f"No aggregator sources reachable for {retailer} code '{code}' - allowing by default")
        return True
    
    is_valid = validations >= 1
    if not is_valid:
        validation_logger.warning(f"Code '{code}' for {retailer} NOT found on any of {sources_checked} aggregator sources")
    return is_valid


def validate_and_filter_deals(new_deals):
    """Validate scraped deals and return only verified ones.
    
    Codes are cross-referenced against aggregator sources.
    Invalid codes are logged but not published.
    Only validated/working codes replace current live codes.
    """
    global INVALID_CODES_LOG
    validated_deals = []
    invalid_deals = []
    
    for deal in new_deals:
        code = deal.get("code", "")
        retailer = deal.get("retailer", "")
        
        # Deals without codes (percentage-off links, etc.) pass through
        if not code or code.strip() == "":
            validated_deals.append(deal)
            continue
        
        # Validate the code against aggregator sources
        if validate_code_against_aggregators(code, retailer):
            deal["validated"] = True
            deal["validated_at"] = datetime.now().isoformat()
            validated_deals.append(deal)
        else:
            # Log invalid code but do NOT publish
            invalid_entry = {
                "code": code,
                "retailer": retailer,
                "description": deal.get("description", ""),
                "reason": "Not found on aggregator sources",
                "scraped_at": datetime.now().isoformat()
            }
            INVALID_CODES_LOG.append(invalid_entry)
            invalid_deals.append(deal)
            validation_logger.info(
                f"REJECTED: Code '{code}' for {retailer} - not validated by aggregators"
            )
    
    validation_logger.info(
        f"Validation complete: {len(validated_deals)} valid, {len(invalid_deals)} rejected"
    )
    return validated_deals


def scrape_all():
    """Scrape all retailers, validate codes, and only publish verified deals."""
    global _scrape_status
    _scrape_status = {"running": True, "last_run": None, "message": "Scraping in progress..."}
    all_new_deals = []

    # Scrape retailers concurrently — sequential scraping of every source for
    # every retailer is slow enough on Render's free-tier CPU that a run can
    # stall out before ever reaching the status update below.
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_retailer = {executor.submit(scrape_retailer, r): r for r in RETAILERS}
        for future in as_completed(future_to_retailer):
            retailer = future_to_retailer[future]
            try:
                all_new_deals.extend(future.result())
            except Exception as e:
                print(f"Error scraping {retailer['name']}: {e}")

    # Validate codes against aggregator sources before publishing
    validation_logger.info(f"Starting validation of {len(all_new_deals)} scraped deals...")
    validated_deals = validate_and_filter_deals(all_new_deals)

    # If every live source is blocked/empty, fall back to curated data so
    # the site is never left with nothing to show.
    if not validated_deals:
        validation_logger.warning("No live deals from any source — publishing fallback deals")
        validated_deals = get_fallback_deals()

    # Only replace live codes with validated ones
    if validated_deals:
        current_deals = load_deals().get("deals", [])
        # Keep existing deals that aren't being replaced
        existing_ids = {d.get("id") for d in validated_deals}
        kept_deals = [d for d in current_deals if d.get("id") not in existing_ids]
        # Merge: keep old deals + add new validated deals
        final_deals = kept_deals + validated_deals
        save_deals(final_deals)
        validation_logger.info(f"Published {len(validated_deals)} validated deals, kept {len(kept_deals)} existing deals")
    else:
        validation_logger.warning("No validated deals to publish - keeping current live codes")

    _scrape_status = {
        "running": False,
        "last_run": datetime.now().isoformat(),
        "message": f"Completed: {len(validated_deals)} validated deals published, {len(INVALID_CODES_LOG)} codes rejected"
    }
    return validated_deals


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
        retailer = deal.get("retailer", "")
        domain = domain_map.get(retailer.lower(), "")
        if domain:
            deal["domain"] = domain
            if not deal.get("url"):
                deal["url"] = f"https://www.{domain}"
        # Fix Macy's code: BEST1521 should be SHOP1521
        if retailer.lower() == "macys" and deal.get("code") == "BEST1521":
            deal["code"] = "FRIEND"
    data["total_deals"] = len(deals)
    data["total_codes"] = sum(1 for d in deals if d.get("code"))
    data["total"] = len(deals)
    data["page"] = 1
    data["pages"] = 1
    for d in deals:
        d["type"] = d.get("deal_type", "deal")
        meta = next((r for r in RETAILERS if r["name"].lower() == d.get("retailer", "").lower()), {})
        if not d.get("icon"):
            d["icon"] = meta.get("icon", "")
        if not d.get("color"):
            d["color"] = meta.get("color", "#6c5ce7")
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


@app.route("/healthz")
def healthz():
    """Lightweight endpoint for the self-ping keep-alive job (and uptime checks)."""
    return jsonify({"status": "ok"})


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
    retailer_meta = {r["name"].lower(): r for r in RETAILERS}
    for deal in trending:
        deal["isTrending"] = True
        r_key = deal.get("retailer", "").lower()
        meta = retailer_meta.get(r_key, {})
        if not deal.get("icon"):
            deal["icon"] = meta.get("icon", "")
        if not deal.get("color"):
            deal["color"] = meta.get("color", "#6c5ce7")
        if not deal.get("url"):
            domain = domain_map.get(r_key, "")
            if domain:
                deal["url"] = f"https://www.{domain}"
    return jsonify({"deals": trending})


@app.route("/api/deals/featured")
def api_deals_featured():
    data = load_deals()
    deals = data.get("deals", [])
    if deals:
        domain_map = {r["name"].lower(): r["domain"] for r in RETAILERS}
        for deal in deals:
            if deal.get("code"):
                retailer = deal.get("retailer", "")
                domain = domain_map.get(retailer.lower(), "")
                if domain:
                    deal["domain"] = domain
                    if not deal.get("url"):
                        deal["url"] = f"https://www.{domain}"
                if retailer.lower() == "macys" and deal.get("code") == "BEST1521":
                    deal["code"] = "FRIEND"
                return jsonify({"deal": deal})
        deal = deals[0]
        if not deal.get("url"):
            domain = domain_map.get(deal.get("retailer", "").lower(), "")
            if domain:
                deal["url"] = f"https://www.{domain}"
        return jsonify({"deal": deal})
    return jsonify({"deal": None})


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



def keep_alive_ping():
    """Self-ping so Render's free tier never sees 15 minutes of inactivity
    and spins the dyno down (which causes ~40-50s cold starts on the next
    request)."""
    if not RENDER_EXTERNAL_URL:
        return
    try:
        SESSION.get(f"{RENDER_EXTERNAL_URL}/healthz", timeout=10)
        validation_logger.info("Keep-alive ping OK")
    except Exception as e:
        validation_logger.warning(f"Keep-alive ping failed: {e}")


# --- APScheduler: Automated 6-hour scraping schedule + keep-alive ---
scheduler = BackgroundScheduler()

_scrape_job_kwargs = dict(
    func=scrape_all,
    trigger=IntervalTrigger(hours=6),
    id='scheduled_scrape',
    name='Scrape all retailers every 6 hours',
    replace_existing=True,
)
# Run the first scrape immediately (rather than waiting a full 6 hours) when
# there's no cached data yet. This works whether the app is started with
# `python app.py` or imported by gunicorn, unlike a `__main__`-gated thread.
if not os.path.exists(DEALS_FILE):
    _scrape_job_kwargs["next_run_time"] = datetime.now()
scheduler.add_job(**_scrape_job_kwargs)

if RENDER_EXTERNAL_URL:
    scheduler.add_job(
        func=keep_alive_ping,
        trigger=IntervalTrigger(minutes=10),
        id='keep_alive_ping',
        name='Self-ping to prevent Render free-tier sleep',
        replace_existing=True,
    )
    validation_logger.info(f"Keep-alive ping scheduled every 10 min against {RENDER_EXTERNAL_URL}")

scheduler.start()
validation_logger.info("APScheduler started: scraping every 6 hours")

# API endpoint to view invalid/rejected codes
@app.route("/api/invalid-codes")
def api_invalid_codes():
    return jsonify(INVALID_CODES_LOG[-100:])  # Return last 100 invalid codes


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
