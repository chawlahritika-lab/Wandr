import pytest
from pydantic import ValidationError

from app.schemas.trip import TripRequest, TripResponse


def test_trip_request_accepts_valid_values():
    payload = {
        "destination": "Kyoto",
        "start_date": "2026-10-12",
        "end_date": "2026-10-18",
        "travelers": 2,
        "persona": "Couple",
        "budget_level": "Midrange",
        "travel_style": "Cultural",
        "interests": ["Food", "History"],
    }

    req = TripRequest(**payload)

    assert req.persona == "Couple"
    assert req.travel_style == "Cultural"
    assert req.interests == ["Food", "History"]


def test_trip_request_rejects_unknown_persona():
    with pytest.raises(ValidationError):
        TripRequest(
            destination="Kyoto",
            start_date="2026-10-12",
            end_date="2026-10-18",
            travelers=2,
            persona="Explorer",
            budget_level="Midrange",
            travel_style="Cultural",
            interests=["Food"],
        )


def test_trip_response_contains_expected_fields():
    response = TripResponse(
        destination="Kyoto",
        narrative="A thoughtful Kyoto trip for a couple focused on food and history.",
        recommendations=[],
        itinerary=[],
        budget_breakdown={"stay": 0, "food": 0, "activities": 0, "transport": 0, "total": 0},
    )

    assert response.destination == "Kyoto"
    assert response.budget_breakdown.total == 0
