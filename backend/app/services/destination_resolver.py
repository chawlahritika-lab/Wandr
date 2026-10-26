from __future__ import annotations

from dataclasses import dataclass

from app.data.destinations import DESTINATION_DATA
from app.services.agent import AgentDecision, resolve_with_agent


@dataclass(frozen=True)
class DestinationResolution:
    canonical_name: str
    confidence: float
    source: str
    rationale: str = ""
    decision: AgentDecision | None = None
    dataset: dict | None = None


ALIASES = {
    "kyoto japan": "Kyoto",
    "kyoto, japan": "Kyoto",
    "lisbon portugal": "Lisbon",
    "lisbon, portugal": "Lisbon",
    "jaipur india": "Jaipur",
    "jaipur, india": "Jaipur",
    "malaysia": "Kuala Lumpur",
    "kuala lumpur malaysia": "Kuala Lumpur",
    "kuala lumpur, malaysia": "Kuala Lumpur",
}


def resolve_destination(value: str, prefer_agent: bool = False) -> DestinationResolution:
    cleaned = " ".join(value.strip().split())

    if prefer_agent:
        decision = resolve_with_agent(cleaned)
        if decision:
            dataset = None
            if decision.destination not in DESTINATION_DATA:
                candidates = [item.model_dump() for item in decision.candidates]
                if len(candidates) < 4:
                    raise ValueError("Wandr could not find enough agent-supplied places to plan this destination.")
                dataset = {
                    "city": decision.destination,
                    "country": decision.country,
                    "currency": decision.currency,
                    "stays": [item for item in candidates if item["category"] == "stay"],
                    "food": [item for item in candidates if item["category"] == "food"],
                    "activities": [item for item in candidates if item["category"] == "activity"],
                    "attractions": [item for item in candidates if item["category"] == "attraction"],
                }
            return DestinationResolution(decision.destination, decision.confidence, "agent", decision.rationale, decision, dataset)

    if cleaned in DESTINATION_DATA:
        return DestinationResolution(cleaned, 1.0, "catalog")

    normalized = cleaned.casefold()
    for alias, canonical_name in ALIASES.items():
        if normalized == alias:
            return DestinationResolution(canonical_name, 0.98, "alias")

    hint_matches = {
        "kyoto": "Kyoto",
        "lisbon": "Lisbon",
        "jaipur": "Jaipur",
    }
    for hint, canonical_name in hint_matches.items():
        if hint in normalized:
            return DestinationResolution(canonical_name, 0.9, "text_hint")

    supported = ", ".join(sorted(DESTINATION_DATA))
    raise ValueError(
        f"We could not resolve '{cleaned}' to a destination yet. "
        f"Try a city name or choose from: {supported}."
    )
