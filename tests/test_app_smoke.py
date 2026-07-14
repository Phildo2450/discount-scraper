import pytest
from datetime import timedelta

from app import (
    app,
    normalize_retailer_key,
    build_deal,
    validate_deal,
    decorate_deal,
    RETAILERS,
    iso_now,
    parse_dt,
    FRESHNESS_WINDOW,
)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_returns_200(client):
    rv = client.get("/")
    assert rv.status_code == 200


def test_api_deals_returns_official_json_shape(client):
    rv = client.get("/api/deals")
    assert rv.status_code == 200
    assert rv.content_type == "application/json"
    data = rv.get_json()
    assert {"deals", "total", "total_codes", "freshness_hours"}.issubset(data)


def test_api_status_returns_json(client):
    rv = client.get("/api/status")
    assert rv.status_code == 200
    assert rv.content_type == "application/json"


def test_api_retailers_returns_600_official_registry_entries(client):
    rv = client.get("/api/retailers")
    assert rv.status_code == 200
    retailers = rv.get_json()
    assert len(retailers) == 600
    assert all("allowed_domains" in r and "promo_paths" in r for r in retailers)
    assert all("logo_url" in r and r["logo_url"].startswith("https://") for r in retailers)
    assert all(isinstance(r.get("popularity_rank"), int) for r in retailers)
    assert [r["popularity_rank"] for r in retailers] == list(range(1, 601))
    assert len({r["domain"] for r in retailers}) == 600
    assert len({r["slug"] for r in retailers}) == 600
    domains = {r["domain"] for r in retailers}
    assert "rakuten.com" not in domains
    assert "capitaloneshopping.com" not in domains


def test_expanded_registry_preserves_curated_original_targets(client):
    retailers = {r["domain"]: r for r in client.get("/api/retailers").get_json()}
    assert "/c/target-deals/-/N-4xw74" in retailers["target.com"]["promo_paths"]
    assert "/site/top-deals" in retailers["bestbuy.com"]["promo_paths"]
    assert retailers["macys.com"]["promo_paths"] == ["/shop/coupons-deals"]
    assert "bestbuy" in retailers["bestbuy.com"].get("keywords", [])
    assert "b&h" in retailers["bhphotovideo.com"].get("keywords", [])
    assert retailers["hm.com"]["slug"] == "h-and-m"
    assert retailers["lowes.com"]["slug"] == "lowes"
    assert retailers["booking.com"]["slug"] == "bookingcom"


def test_source_status_returns_registry_coverage(client):
    rv = client.get("/api/source-status")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["freshness_hours"] == 3
    assert len(data["retailers"]) == 600
    assert all(r.get("logo_url", "").startswith("https://") for r in data["retailers"])


def test_api_categories_cover_registry_not_just_current_deals(client):
    rv = client.get("/api/categories")
    assert rv.status_code == 200
    categories = rv.get_json()
    assert sum(c["count"] for c in categories) == 600
    assert {"fashion", "electronics", "travel", "home", "food"}.issubset({c["category"] for c in categories})


def test_api_scrape_post(client, monkeypatch):
    # Keep the smoke test deterministic and avoid real network scraping in tests.
    import app as app_module

    monkeypatch.setattr(app_module, "scrape_all", lambda: [])
    rv = client.post("/api/scrape")
    assert rv.status_code in (200, 202, 302)


def test_normalize_retailer_key():
    assert normalize_retailer_key("Best Buy") == "bestbuy"
    assert normalize_retailer_key("AMAZON") == "amazon"


def test_build_deal_creates_official_fresh_deal():
    retailer = RETAILERS[0]
    deal = build_deal(
        retailer=retailer,
        description="Use code SAVE20 for 20% off at checkout",
        discount="20% off",
        url=f"https://www.{retailer['domain']}/deals",
        code="SAVE20",
        source=retailer["name"],
    )
    assert deal["retailer"] == retailer["name"]
    assert deal["code"] == "SAVE20"
    assert deal["type"] == "code"
    assert deal["logo_url"].startswith("https://")
    assert deal["popularity_rank"] == retailer["popularity_rank"]
    assert deal["official_source"] is True
    assert validate_deal(deal) is True


def test_build_deal_no_code_is_deal_type():
    retailer = RETAILERS[0]
    deal = build_deal(
        retailer=retailer,
        description="Official sale page checked",
        discount="Official Offers",
        url=f"https://www.{retailer['domain']}/sale",
        code="",
        source=retailer["name"],
    )
    assert deal["type"] == "deal"
    assert validate_deal(deal) is True


def test_scrape_official_site_does_not_publish_generic_homepage_placeholder(monkeypatch):
    import app as app_module

    class FakeResponse:
        url = "https://www.example.com/"
        text = "<html><body><h1>Welcome to Example</h1><p>No sale language here.</p></body></html>"

    retailer = {
        "name": "Example",
        "domain": "example.com",
        "category": "services",
        "color": "#333333",
        "icon": "🧰",
        "promo_paths": ["/"],
        "allowed_domains": ["example.com", "www.example.com"],
        "logo_url": "https://www.google.com/s2/favicons?sz=128&domain=example.com",
    }
    monkeypatch.setattr(app_module, "safe_get_official", lambda url, retailer: FakeResponse())
    assert app_module.scrape_official_site(retailer) == []


def test_validate_deal_rejects_third_party_source():
    retailer = RETAILERS[0]
    deal = build_deal(
        retailer=retailer,
        description="Use code SAVE20 for 20% off",
        discount="20% off",
        url="https://couponfollow.com/site/amazon.com",
        code="SAVE20",
        source="CouponFollow",
    )
    assert validate_deal(deal) is False


def test_validate_deal_rejects_stale_source():
    retailer = RETAILERS[0]
    now = parse_dt(iso_now())
    assert now is not None
    stale = (now - FRESHNESS_WINDOW - timedelta(minutes=1)).isoformat()
    deal = build_deal(
        retailer=retailer,
        description="Use code SAVE20 for 20% off",
        discount="20% off",
        url=f"https://www.{retailer['domain']}/deals",
        code="SAVE20",
        source=retailer["name"],
        source_checked_at=stale,
    )
    assert validate_deal(deal) is False


def test_decorate_deal_adds_retailer_key():
    decorated = decorate_deal({"retailer": "Best Buy"})
    assert decorated["retailer_key"] == "bestbuy"
