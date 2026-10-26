import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.destination_resolver import resolve_destination
from app.services.agent import planning


client = TestClient(app)


def test_resolver_accepts_exact_catalog_destination():
    resolution = resolve_destination("Kyoto")

    assert resolution.canonical_name == "Kyoto"
    assert resolution.source == "catalog"
    assert resolution.confidence == 1.0


def test_resolver_accepts_case_insensitive_alias():
    resolution = resolve_destination("Lisbon, Portugal")

    assert resolution.canonical_name == "Lisbon"
    assert resolution.source == "alias"


def test_resolver_accepts_city_inside_free_text():
    resolution = resolve_destination("a slow cultural week around Kyoto Japan")

    assert resolution.canonical_name == "Kyoto"
    assert resolution.source == "text_hint"


def test_resolver_rejects_unknown_destination_with_guidance():
    with pytest.raises(ValueError, match="choose from"):
        resolve_destination("Somewhere warm with great food")


def test_plan_endpoint_returns_controlled_error_for_unknown_destination():
    response = client.post(
        "/api/trips/plan",
        json={
            "destination": "Somewhere warm with great food",
            "start_date": "2026-10-12",
            "end_date": "2026-10-18",
            "travelers": 2,
            "persona": "Couple",
            "budget_level": "Midrange",
            "travel_style": "Cultural",
            "interests": ["Food"],
        },
    )

    assert response.status_code == 400
    assert "could not resolve" in response.json()["detail"]


def test_agent_decision_resolves_open_brief_with_valid_catalog_destination(monkeypatch):
    class FakeProvider:
        def resolve(self, brief, catalog):
            return planning.AgentDecision(
                destination="Lisbon",
                confidence=0.91,
                rationale="The food and coastal wording fits Lisbon.",
            )

    monkeypatch.setattr(planning, "_provider", lambda: FakeProvider())

    resolution = resolve_destination("a warm city with great food", prefer_agent=True)

    assert resolution.canonical_name == "Lisbon"
    assert resolution.source == "agent"
    assert resolution.rationale.startswith("The food")


def test_agent_decision_rejects_destination_outside_catalog(monkeypatch):
    class FakeProvider:
        def resolve(self, brief, catalog):
            return planning.AgentDecision(
                destination="Atlantis",
                confidence=0.99,
                rationale="An unsafe invented destination.",
            )

    monkeypatch.setattr(planning, "_provider", lambda: FakeProvider())

    with pytest.raises(ValueError, match="enough researched places"):
        resolve_destination("somewhere impossible", prefer_agent=True)


def test_agent_led_plan_applies_validated_profile_before_engine(monkeypatch):
    class FakeProvider:
        def resolve(self, brief, catalog):
            return planning.AgentDecision(
                destination="Jaipur",
                confidence=0.94,
                rationale="The warm food-and-culture brief fits Jaipur.",
                persona="Backpacker",
                budget_level="Budget",
                travel_style="Foodie",
                interests=["Food", "History"],
            )

    monkeypatch.setattr(planning, "_provider", lambda: FakeProvider())
    response = client.post(
        "/api/trips/plan",
        json={
            "destination": "warm food and culture",
            "agent_decides": True,
            "start_date": "2026-10-12",
            "end_date": "2026-10-14",
            "travelers": 5,
            "persona": "Couple",
            "budget_level": "Midrange",
            "travel_style": "Cultural",
            "interests": ["Food"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["destination"] == "Jaipur"
    assert data["persona"] == "Backpacker"
    assert data["budget_level"] == "Budget"
    assert data["travel_style"] == "Foodie"
    assert data["resolution_source"] == "agent"


def test_agent_plan_includes_user_profile_hints(monkeypatch):
    captured = {}

    class FakeProvider:
        def resolve(self, brief, catalog):
            captured["brief"] = brief
            return planning.AgentDecision(
                destination="Kyoto",
                confidence=0.9,
                rationale="Kyoto fits the request.",
            )

    monkeypatch.setattr(planning, "_provider", lambda: FakeProvider())
    response = client.post(
        "/api/trips/plan",
        json={
            "destination": "Rishikesh",
            "agent_decides": True,
            "start_date": "2026-10-12",
            "end_date": "2026-10-14",
            "travelers": 2,
            "persona": "Family",
            "budget_level": "Budget",
            "travel_style": "Adventurous",
            "interests": ["Nature", "Adventure"],
        },
    )

    assert response.status_code == 200
    assert "persona=Family" in captured["brief"]
    assert "budget=Budget" in captured["brief"]
    assert "style=Adventurous" in captured["brief"]
    assert "interests=Nature, Adventure" in captured["brief"]


def test_agent_parser_accepts_fenced_json_response():
    decision = planning._parse_decision(
        '```json\n{"destination":"Kyoto","confidence":0.9,"rationale":"A good fit."}\n```'
    )

    assert decision.destination == "Kyoto"
    assert decision.confidence == 0.9


def test_agent_parser_normalizes_provider_synonyms():
    decision = planning._parse_decision(
        {
            "destination": "Lisbon",
            "confidence": 0.9,
            "rationale": "A good fit.",
            "budget_level": "moderate",
            "travel_style": "food-focused",
            "interests": ["food and dining", "local markets"],
        }
    )

    assert decision.budget_level == "Midrange"
    assert decision.travel_style == "Foodie"
    assert decision.interests == ["Food", "Shopping"]


def test_agent_parser_normalizes_descriptive_interest_phrases():
    decision = planning._parse_decision(
        {
            "destination": "Lisbon",
            "confidence": 0.9,
            "rationale": "A good fit.",
            "interests": ["Coastal Nature", "Outdoor Walks", "Cultural Atmosphere"],
        }
    )

    assert decision.interests == ["Nature", "History"]


def test_agent_parser_falls_back_for_descriptive_profile_labels():
    decision = planning._parse_decision(
        {
            "destination": "Lisbon",
            "confidence": 0.9,
            "rationale": "A good fit.",
            "persona": "Culture-Curious Nature Lover",
            "budget_level": "Moderate To High",
            "travel_style": "Experiential",
            "interests": ["Coastal Nature", "Outdoor Walks", "Cultural Atmosphere"],
        }
    )

    assert decision.persona is None
    assert decision.budget_level == "Midrange"
    assert decision.travel_style == "Cultural"


def test_agent_parser_flattens_category_based_research_response():
    decision = planning._parse_decision(
        {
            "destination": "Chiang Mai",
            "country": "Thailand",
            "currency": "THB",
            "confidence": 0.9,
            "rationale": "A good fit.",
            "stays": [{"name": "Old City Hotel", "cost": 1200, "area": "Old City"}],
            "food": [{"name": "Night Bazaar Food Walk", "cost": 450, "area": "Night Bazaar"}],
            "activities": [{"name": "Doi Suthep Visit", "cost": 600, "area": "Mountain"}],
            "attractions": [{"name": "Old City Temples", "cost": 0.1, "area": "Old City"}],
        }
    )

    assert len(decision.candidates) == 4
    assert {item.category for item in decision.candidates} == {"stay", "food", "activity", "attraction"}


def test_agent_parser_normalizes_free_researched_places():
    decision = planning._parse_decision(
        {
            "destination": "Rishikesh",
            "country": "India",
            "currency": "INR",
            "confidence": 0.9,
            "rationale": "A strong nature and adventure match.",
            "attractions": [{"name": "Triveni Ghat", "cost": 0, "area": "Rishikesh"}],
        }
    )

    assert decision.candidates[0].price == 1


def test_agent_parser_skips_invalid_researched_candidates():
    decision = planning._parse_decision(
        {
            "destination": "Rishikesh",
            "confidence": 0.9,
            "rationale": "A strong nature and adventure match.",
            "candidates": [
                {"id": "free-ghat", "category": "attraction", "title": "Triveni Ghat", "description": "A riverside evening ceremony.", "price": 0, "rating": 4.5, "location": "Rishikesh"},
                {"id": "missing-title", "category": "activity", "price": 100},
            ],
        }
    )

    assert [item.id for item in decision.candidates] == ["free-ghat"]
    assert decision.candidates[0].price == 1


def test_agent_researched_destination_flows_through_deterministic_engine(monkeypatch):
    class FakeProvider:
        def resolve(self, brief, catalog):
            return planning.AgentDecision(
                destination="Marrakesh",
                country="Morocco",
                currency="MAD",
                confidence=0.93,
                rationale="A strong warm food and culture match.",
                candidates=[
                    planning.AgentCandidate(id="marrakesh-stay-1", category="stay", title="Medina Riad", description="A central riad.", price=900, rating=4.6, location="Medina", tags=["culture", "food"]),
                    planning.AgentCandidate(id="marrakesh-food-1", category="food", title="Souk Food Walk", description="A guided food route.", price=300, rating=4.7, location="Medina", tags=["food", "local"]),
                    planning.AgentCandidate(id="marrakesh-activity-1", category="activity", title="Atlas Day Trip", description="A mountain escape.", price=700, rating=4.5, location="Atlas", tags=["nature", "adventure"]),
                    planning.AgentCandidate(id="marrakesh-attraction-1", category="attraction", title="Bahia Palace", description="A historic palace.", price=100, rating=4.6, location="Kasbah", tags=["history", "culture"]),
                ],
            )

    monkeypatch.setattr(planning, "_provider", lambda: FakeProvider())
    response = client.post(
        "/api/trips/plan",
        json={
            "destination": "Marrakesh Morocco",
            "brief": "a warm food and culture trip in Marrakesh",
            "agent_decides": True,
            "start_date": "2026-10-12",
            "end_date": "2026-10-14",
            "travelers": 2,
            "persona": "Couple",
            "budget_level": "Midrange",
            "travel_style": "Cultural",
            "interests": ["Food", "History"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["destination"] == "Marrakesh"
    assert data["currency"] == "MAD"
    assert data["resolution_source"] == "agent_research"
    assert all(item["id"].startswith("marrakesh-") for item in data["recommendations"])
