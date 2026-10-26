from fastapi.testclient import TestClient

from app.main import app
from app.schemas.trip import TripRequest
from app.services.trip_engine import BUDGET_THRESHOLDS, plan_trip

client = TestClient(app)


def test_currency_rates_endpoint_returns_static_table():
    response = client.get("/api/currency/rates")

    assert response.status_code == 200
    data = response.json()
    assert data["base"] == "USD"
    for code in ("USD", "JPY", "EUR", "INR", "MYR"):
        assert code in data["rates"]


def test_budget_thresholds_endpoint_matches_engine_constants():
    response = client.get("/api/currency/budget-thresholds")

    assert response.status_code == 200
    assert response.json() == BUDGET_THRESHOLDS


def test_researched_destination_gets_default_place_details():
    request = TripRequest(
        destination="Iceland",
        start_date="2026-10-10",
        end_date="2026-10-14",
        travelers=2,
        persona="Couple",
        budget_level="Midrange",
        travel_style="Cultural",
        interests=["Food", "History"],
    )
    researched_data = {
        "currency": "ISK",
        "stays": [{"id": "stay", "title": "Stay", "description": "A stay.", "price": 5000, "rating": 4.5, "location": "Reykjavik", "tags": ["quiet"]}],
        "food": [{"id": "food", "title": "Food", "description": "A meal.", "price": 4000, "rating": 4.5, "location": "Reykjavik", "tags": ["food"]}],
        "activities": [{"id": "activity", "title": "Hike", "description": "A hike.", "price": 3000, "rating": 4.5, "location": "Reykjavik", "tags": ["nature"]}],
        "attractions": [{"id": "attraction", "title": "Museum", "description": "A museum.", "price": 2800, "rating": 4.5, "location": "Reykjavik", "tags": ["history"]}],
    }

    trip = plan_trip(request, destination_data=researched_data)

    assert trip.recommendations
    for item in trip.recommendations:
        assert item.reviews
        assert item.crowd_density == "Medium"
        assert item.best_time_to_visit
        assert item.popularity == "Popular"
