from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.config import settings
from app.data.destinations import DESTINATION_DATA
from app.schemas.trip import BudgetLevel, Interest, Persona, TravelStyle

logger = logging.getLogger(__name__)

DESTINATION_ALIASES = {
    "malaysia": "Kuala Lumpur",
    "kuala lumpur malaysia": "Kuala Lumpur",
    "kuala lumpur, malaysia": "Kuala Lumpur",
}


class AgentDecision(BaseModel):
    destination: str = Field(min_length=2)
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=500)
    persona: Persona | None = None
    budget_level: BudgetLevel | None = None
    travel_style: TravelStyle | None = None
    interests: list[Interest] = Field(default_factory=list, max_length=6)
    country: str = ""
    currency: str = Field(default="USD", min_length=3, max_length=3)
    candidates: list["AgentCandidate"] = Field(default_factory=list, max_length=40)


class AgentCandidate(BaseModel):
    id: str = Field(min_length=2)
    category: str
    title: str = Field(min_length=2)
    description: str = Field(min_length=2)
    price: float = Field(gt=0)
    rating: float = Field(ge=0, le=5)
    location: str = Field(min_length=2)
    tags: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("price", mode="before")
    @classmethod
    def normalize_price(cls, value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            match = re.search(r"[0-9]+(?:[.,][0-9]+)?", value.replace(",", ""))
            if match:
                return float(match.group())
        raise ValueError("candidate price must contain a numeric amount")

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        category = value.casefold().rstrip("s")
        if category not in {"stay", "food", "activity", "attraction"}:
            raise ValueError("candidate category must be stay, food, activity, or attraction")
        return category


class PlanningProvider(Protocol):
    def resolve(self, brief: str, catalog: list[str]) -> AgentDecision:
        ...


SYSTEM_PROMPT = (
    "You are Wandr's travel planning interpreter. Return JSON only with keys: "
    "destination, confidence, rationale, persona, budget_level, travel_style, interests. "
    "For a destination in the catalog, candidates may be omitted. For a destination "
    "outside it, research the destination and return exactly 4 concise candidate objects: "
    "one each for stay, food, activity, and attraction. Each object must have exactly "
    "id, category, title, description (max 12 words), numeric price with no currency text, rating, location, and tags "
    "(max 4 tags). Use realistic local-currency prices and never claim availability. "
    "Also return country and a 3-letter ISO currency code. Return only the requested JSON. "
    "Keep confidence between 0 and 1."
)


def _prompt(brief: str, catalog: list[str]) -> str:
    return f"Curated catalog: {', '.join(catalog)}\nUser brief: {brief}"


def _parse_decision(value: Any) -> AgentDecision:
    if isinstance(value, str):
        content = value.strip()
        fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.IGNORECASE | re.DOTALL)
        if fenced_match:
            content = fenced_match.group(1).strip()
        if not content.startswith("{"):
            start = content.find("{")
            end = content.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("The planning agent returned no JSON object")
            content = content[start:end + 1]
        value = json.loads(content)
    if isinstance(value, dict):
        value = _normalize_decision(value)
        valid_candidates = []
        for candidate in value.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            candidate = dict(candidate)
            if isinstance(candidate.get("price"), (int, float)) and candidate["price"] <= 0:
                candidate["price"] = 1
            try:
                valid_candidates.append(AgentCandidate.model_validate(candidate).model_dump())
            except ValidationError:
                continue
        value["candidates"] = valid_candidates
    return AgentDecision.model_validate(value)


def _post_agent_request(url: str, **kwargs: Any) -> httpx.Response:
    last_error: httpx.TimeoutException | None = None
    for attempt in range(2):
        try:
            return httpx.post(url, **kwargs)
        except httpx.TimeoutException as error:
            last_error = error
            logger.warning("Planning agent timed out on attempt %s/2", attempt + 1)
    raise last_error or httpx.TimeoutException("Planning agent request timed out")


def _normalize_decision(value: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(value)
    if isinstance(normalized.get("destination"), str):
        destination_key = normalized["destination"].strip().casefold()
        normalized["destination"] = DESTINATION_ALIASES.get(destination_key, normalized["destination"].strip())
    if not normalized.get("candidates"):
        candidates = []
        category_map = {"stays": "stay", "food": "food", "activities": "activity", "attractions": "attraction"}
        for category in category_map:
            for index, item in enumerate(normalized.get(category, [])):
                if not isinstance(item, dict):
                    continue
                candidate = dict(item)
                candidate["id"] = candidate.get("id") or f"researched-{category}-{index + 1}"
                candidate["category"] = category_map[category]
                candidate["title"] = candidate.get("title") or candidate.get("name")
                candidate["price"] = next(
                    (
                        candidate[field]
                        for field in ("price", "estimated_price", "cost")
                        if candidate.get(field) is not None
                    ),
                    1,
                )
                if isinstance(candidate["price"], (int, float)) and candidate["price"] <= 0:
                    candidate["price"] = 1
                candidate["description"] = candidate.get("description") or candidate.get("summary") or candidate.get("why") or "A researched option for this route."
                candidate["location"] = candidate.get("location") or candidate.get("area") or "Central district"
                candidate["rating"] = candidate.get("rating") or 4.3
                candidate["tags"] = candidate.get("tags") or []
                candidates.append(candidate)
        normalized["candidates"] = candidates
    valid_profiles = {
        "persona": {"Solo", "Student", "Couple", "Honeymoon", "Family", "Backpacker"},
        "budget_level": {"Budget", "Midrange", "Premium", "Luxe"},
        "travel_style": {"Relaxed", "Adventurous", "Cultural", "Luxury", "Foodie", "Wellness"},
    }
    aliases = {
        "moderate": "Midrange",
        "mid-range": "Midrange",
        "mid range": "Midrange",
        "cheap": "Budget",
        "expensive": "Premium",
        "high-end": "Luxe",
        "leisurely": "Relaxed",
        "slow": "Relaxed",
        "culture": "Cultural",
        "food-focused": "Foodie",
        "food focused": "Foodie",
        "moderate to high": "Midrange",
        "moderate-high": "Midrange",
        "experiential": "Cultural",
        "experience-led": "Cultural",
    }
    for field in ("persona", "budget_level", "travel_style"):
        current = normalized.get(field)
        if isinstance(current, str):
            lowered = current.casefold()
            normalized[field] = aliases.get(lowered, current.title())
            if field == "persona" and "foodie" in lowered:
                normalized[field] = None
            if field == "persona" and any(word in lowered for word in ("traveler", "traveller", "explorer")):
                normalized[field] = None
            if field == "persona" and any(word in lowered for word in ("duo", "couple", "pair")):
                normalized[field] = "Couple"
            if field == "travel_style" and "cultural" in lowered:
                normalized[field] = "Cultural"
            if field == "travel_style" and "relaxed" in lowered:
                normalized[field] = "Relaxed"
            if field == "travel_style" and "slow" in lowered:
                normalized[field] = "Relaxed"
            if normalized[field] not in valid_profiles[field]:
                normalized[field] = None

    interest_aliases = {
        "food and dining": "Food",
        "warm weather": "Nature",
        "local markets": "Shopping",
        "culture": "History",
        "café culture": "History",
        "cafe culture": "History",
        "cafes": "Food",
        "café": "Food",
        "cafe": "Food",
        "cultural dining experiences": "Food",
        "historic neighborhoods": "History",
        "cultural walks": "History",
        "architecture": "Art",
        "night life": "Nightlife",
    }
    if isinstance(normalized.get("interests"), str):
        normalized["interests"] = [normalized["interests"]]
    if isinstance(normalized.get("interests"), list):
        valid_interests = {"Food", "History", "Nature", "Nightlife", "Shopping", "Adventure", "Wellness", "Art", "Photography", "Family"}
        mapped_interests = []
        for item in normalized["interests"]:
            if not isinstance(item, str):
                continue
            lowered = item.casefold()
            mapped = interest_aliases.get(lowered)
            if not mapped and item.title() in valid_interests:
                mapped = item.title()
            if not mapped:
                keyword_map = (
                    (("food", "cuisine", "cafe", "dining", "market"), "Food"),
                    (("history", "historic", "heritage", "cultural", "atmosphere"), "History"),
                    (("nature", "coastal", "outdoor", "walk", "beach", "scenic"), "Nature"),
                    (("night", "bar", "music"), "Nightlife"),
                    (("shop", "bazaar", "retail"), "Shopping"),
                    (("adventure", "hike", "surf", "trail"), "Adventure"),
                    (("wellness", "spa", "yoga", "relax"), "Wellness"),
                    (("art", "museum", "gallery", "architecture"), "Art"),
                    (("photo", "photograph"), "Photography"),
                    (("family", "kids", "children"), "Family"),
                )
                mapped = next((category for keywords, category in keyword_map if any(keyword in lowered for keyword in keywords)), None)
            if mapped:
                mapped_interests.append(mapped)
        normalized["interests"] = list(dict.fromkeys(mapped_interests))[:6]
    return normalized


class AzureOpenAIProvider:
    def resolve(self, brief: str, catalog: list[str]) -> AgentDecision:
        if not settings.azure_openai_endpoint or not settings.azure_openai_api_key or not settings.azure_openai_deployment:
            raise RuntimeError("Azure OpenAI is not fully configured")
        endpoint = settings.azure_openai_endpoint.rstrip("/")
        url = f"{endpoint}/openai/deployments/{settings.azure_openai_deployment}/chat/completions"
        response = _post_agent_request(
            url,
            params={"api-version": settings.azure_openai_api_version},
            headers={"api-key": settings.azure_openai_api_key},
            json={
                "temperature": 0,
                "max_tokens": 1400,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _prompt(brief, catalog)},
                ],
            },
            timeout=settings.agent_timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return _parse_decision(content)


class AnthropicProvider:
    def resolve(self, brief: str, catalog: list[str]) -> AgentDecision:
        if not settings.anthropic_api_key:
            raise RuntimeError("Anthropic is not configured")
        response = _post_agent_request(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": settings.anthropic_api_version,
                "content-type": "application/json",
            },
            json={
                "model": settings.anthropic_model,
                "max_tokens": 500,
                "temperature": 0,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": _prompt(brief, catalog)}],
            },
            timeout=settings.agent_timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["content"][0]["text"]
        return _parse_decision(content)


class GroqProvider:
    def resolve(self, brief: str, catalog: list[str]) -> AgentDecision:
        if not settings.groq_api_key:
            raise RuntimeError("Groq is not configured")
        response = _post_agent_request(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "content-type": "application/json",
            },
            json={
                "model": settings.groq_model,
                "temperature": 0,
                "max_tokens": 1400,
                # gpt-oss is a reasoning model: without this, it can spend most of
                # max_tokens on hidden reasoning and truncate the actual JSON answer.
                "reasoning_effort": "low",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _prompt(brief, catalog)},
                ],
            },
            timeout=settings.agent_timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return _parse_decision(content)


def _provider() -> PlanningProvider | None:
    if settings.groq_api_key:
        return GroqProvider()
    if settings.azure_openai_endpoint and settings.azure_openai_api_key and settings.azure_openai_deployment:
        return AzureOpenAIProvider()
    if settings.anthropic_api_key:
        return AnthropicProvider()
    return None


def resolve_with_agent(brief: str) -> AgentDecision | None:
    provider = _provider()
    if provider is None:
        logger.info("Planning agent disabled: no supported provider is configured")
        return None
    try:
        decision = provider.resolve(brief, sorted(DESTINATION_DATA))
    except ValidationError as error:
        logger.warning("Planning agent returned invalid structured data: %s", error)
        raise ValueError("The planning agent returned an incomplete travel profile. Please add more detail and try again.") from error
    except json.JSONDecodeError as error:
        logger.warning("Planning agent returned invalid JSON: %s", error)
        raise ValueError("The planning agent returned an unreadable response. Please try again.") from error
    except (KeyError, RuntimeError, ValueError, httpx.HTTPError) as error:
        logger.warning("Planning agent request failed: %s", error)
        raise ValueError(f"The planning agent could not resolve this brief: {error}") from error
    if decision.confidence < settings.agent_min_confidence:
        raise ValueError("Wandr needs a little more detail before choosing a destination.")
    return decision
