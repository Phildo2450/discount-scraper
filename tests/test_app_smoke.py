import pytest
from app import app, normalize_retailer_key, build_deal, validate_deal, decorate_deal


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ---- Route smoke tests ----

def test_index_returns_200(client):
    """GET / should return 200."""
    rv = client.get("/")
    assert rv.status_code == 200


def test_api_deals_returns_json(client):
    """GET /api/deals should return JSON."""
    rv = client.get("/api/deals")
    assert rv.status_code == 200
    assert rv.content_type == "application/json"


def test_api_status_returns_json(client):
    """GET /api/status should return JSON."""
    rv = client.get("/api/status")
    assert rv.status_code == 200
    assert rv.content_type == "application/json"


def test_api_retailers_returns_json(client):
    """GET /api/retailers should return JSON."""
    rv = client.get("/api/retailers")
    assert rv.status_code == 200
    assert rv.content_type == "application/json"


def test_api_scrape_post(client):
    """POST /api/scrape should accept request."""
    rv = client.post("/api/scrape")
    assert rv.status_code in (200, 202, 302)


# ---- Helper function tests ----

def test_normalize_retailer_key():
    """normalize_retailer_key should lowercase and strip spaces."""
    assert normalize_retailer_key("Best Buy") == "best_buy"
    assert normalize_retailer_key("AMAZON") == "amazon"


def test_build_deal_creates_valid_deal():
    """build_deal should return a dict with required keys."""
    deal = build_deal(
        title="50% off shoes",
        retailer="Nike",
        discount="50%",
        url="https://nike.com/deal",
        code="SAVE50"
    )
    assert isinstance(deal, dict)
    assert deal["title"] == "50% off shoes"
    assert deal["retailer"] == "Nike"
    assert deal["code"] == "SAVE50"
    assert deal["type"] == "code"


def test_build_deal_no_code_is_deal_type():
    """build_deal with no code should have type deal."""
    deal = build_deal(
        title="Free shipping",
        retailer="Amazon",
        discount="Free shipping",
        url="https://amazon.com/deal",
        code=""
    )
    assert deal["type"] == "deal"


def test_validate_deal_valid():
    """validate_deal should return True for a complete deal."""
    deal = {
        "title": "Test deal",
        "retailer": "TestStore",
        "discount": "20%",
        "url": "https://example.com",
        "type": "deal"
    }
    assert validate_deal(deal) is True


def test_validate_deal_missing_fields():
    """validate_deal should return False if required fields missing."""
    deal = {"title": "Incomplete"}
    assert validate_deal(deal) is False


def test_decorate_deal_adds_retailer_key():
    """decorate_deal should add retailer_key field."""
    deal = {
        "title": "Test",
        "retailer": "Best Buy",
        "discount": "10%",
        "url": "https://bestbuy.com",
        "type": "code",
        "code": "BB10"
    }
    decorated = decorate_deal(deal)
    assert "retailer_key" in decorated
    assert decorated["retailer_key"] == "best_buy"
