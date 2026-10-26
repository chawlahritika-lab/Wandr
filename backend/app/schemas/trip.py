from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Persona = Literal["Solo", "Student", "Couple", "Honeymoon", "Family", "Backpacker"]
BudgetLevel = Literal["Budget", "Midrange", "Premium", "Luxe"]
TravelStyle = Literal["Relaxed", "Adventurous", "Cultural", "Luxury", "Foodie", "Wellness"]
Interest = Literal[
    "Food",
    "History",
    "Nature",
    "Nightlife",
    "Shopping",
    "Adventure",
    "Wellness",
    "Art",
    "Photography",
    "Family",
]


class TripRequest(BaseModel):
    destination: str = Field(..., min_length=2, max_length=120)
    brief: str | None = Field(default=None, max_length=500)
    agent_decides: bool = False
    start_date: date
    end_date: date
    travelers: int = Field(..., ge=1, le=12)
    persona: Persona
    budget_level: BudgetLevel
    travel_style: TravelStyle
    interests: list[Interest] = Field(..., min_length=1, max_length=6)
    # USD-denominated total-trip-budget target; converted to the destination's actual
    # currency server-side (see trip_engine.usd_to_local) before use.
    price_min: float | None = Field(default=None, ge=0)
    price_max: float | None = Field(default=None, ge=0)
    custom_places: list[str] = Field(default_factory=list, max_length=10)
    preference_notes: str | None = Field(default=None, max_length=500)

    @field_validator("end_date")
    @classmethod
    def validate_end_date_after_start(cls, value: date, info):
        start = info.data.get("start_date")
        if start and value < start:
            raise ValueError("end_date must be on or after start_date")
        return value

    @field_validator("price_max")
    @classmethod
    def validate_price_range(cls, value: float | None, info):
        price_min = info.data.get("price_min")
        if value is not None and price_min is not None and value < price_min:
            raise ValueError("price_max must be greater than or equal to price_min")
        return value

    @field_validator("custom_places")
    @classmethod
    def clean_custom_places(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(place.strip() for place in value if place.strip()))

    @field_validator("preference_notes")
    @classmethod
    def clean_preference_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class RecommendationItem(BaseModel):
    id: str
    category: str
    title: str
    description: str
    price: float
    tags: list[str] = Field(default_factory=list)
    rating: float = Field(ge=0, le=5)
    location: str
    persona_fit: float = 0.0
    interest_match: float = 0.0
    budget_fit: float = 0.0
    style_fit: float = 0.0
    preference_match: float = 0.0
    score: float = 0.0
    reason: str = ""
    reviews: list[str] = Field(default_factory=list)
    crowd_density: str = "Medium"
    best_time_to_visit: str = ""
    popularity: str = "Popular"


class ItineraryDay(BaseModel):
    day: int
    title: str
    summary: str
    activities: list[str]


class BudgetBreakdown(BaseModel):
    stay: float
    food: float
    activities: float
    transport: float
    total: float


class TripResponse(BaseModel):
    destination: str
    persona: Persona = "Couple"
    budget_level: BudgetLevel = "Midrange"
    travel_style: TravelStyle = "Cultural"
    interests: list[Interest] = Field(default_factory=list)
    travelers: int = 1
    trip_days: int = 1
    currency: str = ""
    resolution_source: str = "catalog"
    resolution_confidence: float = 1.0
    agent_rationale: str = ""
    narrative: str
    recommendations: list[RecommendationItem] = Field(default_factory=list)
    itinerary: list[ItineraryDay] = Field(default_factory=list)
    budget_breakdown: BudgetBreakdown
    custom_places: list[str] = Field(default_factory=list)
