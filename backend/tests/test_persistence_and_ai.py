from fastapi.testclient import TestClient

from app.main import app
from app.schemas.trip import TripRequest
from app.services.ai_personalization import generate_personalization
from app.services.persistence import list_saved_trips, save_trip


def test_planning_does_not_save_trip():
    before_ids = {item["id"] for item in list_saved_trips()}
    response = TestClient(app).post(
        "/api/trips/plan",
        json={
            "destination": "Kyoto",
            "start_date": "2026-10-12",
            "end_date": "2026-10-18",
            "travelers": 2,
            "persona": "Couple",
            "budget_level": "Midrange",
            "travel_style": "Cultural",
            "interests": ["Food", "History"],
        },
    )

    assert response.status_code == 200
    assert {item["id"] for item in list_saved_trips()} == before_ids


def test_save_trip_round_trip():
    trip = {
        "destination": "Kyoto",
        "narrative": "A Kyoto trip for a couple.",
        "recommendations": [],
        "itinerary": [],
        "budget_breakdown": {"stay": 0, "food": 0, "activities": 0, "transport": 0, "total": 0},
    }
    saved_id = save_trip(trip)
    trips = list_saved_trips()

    assert saved_id is not None
    assert any(item["destination"] == "Kyoto" for item in trips)


def test_save_trip_deduplicates_identical_payloads():
    trip = {
        "destination": "Lisbon",
        "narrative": "A Lisbon trip for a couple.",
        "recommendations": [],
        "itinerary": [],
        "budget_breakdown": {"stay": 0, "food": 0, "activities": 0, "transport": 0, "total": 0},
    }

    first_id = save_trip(trip)
    second_id = save_trip(trip)

    assert second_id == first_id
    assert sum(item["destination"] == "Lisbon" for item in list_saved_trips()) == 1


def test_generate_personalization_falls_back_without_api_key():
    response = generate_personalization(
        destination="Kyoto",
        persona="Couple",
        interests=["Food", "History"],
        top_recommendations=["Gion Courtyard Inn", "Kaiseki Tasting Menu"],
        api_key=None,
    )

    assert "Kyoto" in response
    assert "couple" in response.lower()
