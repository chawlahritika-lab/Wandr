from app.schemas.trip import TripRequest
from app.services.destination_resolver import resolve_destination
from app.services.trip_engine import plan_trip


def build_request(**overrides):
    payload = {
        "destination": "Kuala Lumpur",
        "start_date": "2026-10-10",
        "end_date": "2026-10-14",
        "travelers": 5,
        "persona": "Backpacker",
        "budget_level": "Midrange",
        "travel_style": "Adventurous",
        "interests": ["Food", "Nature", "Adventure"],
    }
    payload.update(overrides)
    return TripRequest(**payload)


def test_malaysia_resolves_to_kuala_lumpur():
    resolution = resolve_destination("Malaysia")

    assert resolution.canonical_name == "Kuala Lumpur"
    assert resolution.source == "alias"


def test_kuala_lumpur_generates_real_malaysian_plan():
    trip = plan_trip(build_request())

    assert trip.destination == "Kuala Lumpur"
    assert trip.currency == "MYR"
    assert trip.recommendations
    assert all("kuala-lumpur" in item.id for item in trip.recommendations)
    assert trip.budget_breakdown.total > 0


def test_researched_local_currency_candidates_are_not_dropped_by_catalog_cap():
    request = build_request(destination="Iceland")
    researched_data = {
        "currency": "ISK",
        "stays": [{"id": "stay", "title": "Stay", "description": "A stay.", "price": 50000, "rating": 4.5, "location": "Reykjavik", "tags": ["quiet"]}],
        "food": [{"id": "food", "title": "Food", "description": "A meal.", "price": 4000, "rating": 4.5, "location": "Reykjavik", "tags": ["food"]}],
        "activities": [{"id": "activity", "title": "Hike", "description": "A hike.", "price": 12000, "rating": 4.5, "location": "Reykjavik", "tags": ["nature"]}],
        "attractions": [{"id": "attraction", "title": "Museum", "description": "A museum.", "price": 2800, "rating": 4.5, "location": "Reykjavik", "tags": ["history"]}],
    }

    trip = plan_trip(request, destination_data=researched_data)

    assert len(trip.recommendations) == 4
