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


def test_api_retailers_returns_101_official_registry_entries(client):
    rv = client.get("/api/retailers")
    assert rv.status_code == 200
    retailers = rv.get_json()
    assert len(retailers) == 101
    assert all("allowed_domains" in r and "promo_paths" in r for r in retailers)


def test_source_status_returns_registry_coverage(client):
    rv = client.get("/api/source-status")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["freshness_hours"] == 3
    assert len(data["retailers"]) == 101


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
