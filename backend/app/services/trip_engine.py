from __future__ import annotations

import re

from app.data.destinations import DESTINATION_DATA
from app.data.exchange_rates import EXCHANGE_RATES_USD
from app.schemas.trip import BudgetBreakdown, ItineraryDay, RecommendationItem, TripRequest, TripResponse

DEFAULT_REVIEWS = [
    "\"A solid pick that matched the description well.\"",
    "\"Would recommend to other travellers with similar interests.\"",
]
DEFAULT_CROWD_DENSITY = "Medium"
DEFAULT_BEST_TIME_TO_VISIT = "Check local seasonal guidance for the best time to visit."
DEFAULT_POPULARITY = "Popular"

PERSONA_WEIGHTS = {
    "Solo": {"budget": 0.9, "social": 0.4, "culture": 0.8, "adventure": 1.0, "wellness": 0.7, "food": 0.6, "history": 0.7},
    "Student": {"budget": 1.0, "social": 0.9, "culture": 0.7, "adventure": 0.8, "food": 0.7, "nightlife": 0.8, "history": 0.5},
    "Couple": {"budget": 0.8, "culture": 0.9, "romance": 1.0, "food": 0.9, "wellness": 0.7, "history": 0.8, "nature": 0.6},
    "Honeymoon": {"budget": 0.6, "romance": 1.0, "luxury": 0.9, "wellness": 0.8, "food": 0.7, "culture": 0.8, "nature": 0.7},
    "Family": {"budget": 0.8, "family": 1.0, "culture": 0.8, "nature": 0.9, "wellness": 0.6, "food": 0.7, "history": 0.6},
    "Backpacker": {"budget": 1.0, "social": 0.9, "adventure": 1.0, "culture": 0.6, "food": 0.7, "history": 0.5, "nightlife": 0.8},
}

INTEREST_TAG_MAP = {
    "Food": ["food"],
    "History": ["history", "culture"],
    "Nature": ["nature"],
    "Nightlife": ["nightlife", "social"],
    "Shopping": ["shopping", "local"],
    "Adventure": ["adventure"],
    "Wellness": ["wellness", "relaxing"],
    "Art": ["culture", "photography"],
    "Photography": ["photography"],
    "Family": ["family", "social"],
}

STYLE_CONSTRAINTS = {
    "Relaxed": {"max_activities_per_day": 2, "buffer_minutes": 90, "pace": "gentle"},
    "Adventurous": {"max_activities_per_day": 4, "buffer_minutes": 40, "pace": "fast"},
    "Cultural": {"max_activities_per_day": 3, "buffer_minutes": 60, "pace": "balanced"},
    "Luxury": {"max_activities_per_day": 2, "buffer_minutes": 110, "pace": "slow"},
    "Foodie": {"max_activities_per_day": 3, "buffer_minutes": 50, "pace": "social"},
    "Wellness": {"max_activities_per_day": 2, "buffer_minutes": 80, "pace": "restful"},
}

STYLE_TAG_MAP = {
    "Relaxed": {"quiet", "wellness", "relaxing", "nature", "scenic"},
    "Adventurous": {"adventure", "nature", "social"},
    "Cultural": {"culture", "heritage", "history", "local"},
    "Luxury": {"luxury", "romance", "scenic", "quiet"},
    "Foodie": {"food", "local", "social"},
    "Wellness": {"wellness", "relaxing", "quiet", "nature"},
}

# USD-denominated reference thresholds. These are converted into whatever currency
# a given destination actually prices in (see usd_to_local) before being compared
# against item prices — applying them as raw numbers regardless of currency would
# make "Budget" mean roughly $13 for a JPY destination but ~$2,170 for a EUR one.
BUDGET_THRESHOLDS = {
    "Budget": 2000,
    "Midrange": 6000,
    "Premium": 12000,
    "Luxe": 25000,
}


def usd_to_local(amount_usd: float, currency: str) -> float:
    return amount_usd * EXCHANGE_RATES_USD.get(currency, 1.0)


def extract_features(request: TripRequest) -> tuple[dict[str, float], set[str], dict[str, float]]:
    persona_weights = PERSONA_WEIGHTS[request.persona]
    interest_tags = {tag for interest in request.interests for tag in INTEREST_TAG_MAP.get(interest, [])}
    style_constraints = STYLE_CONSTRAINTS[request.travel_style]
    return persona_weights, interest_tags, style_constraints


def generate_candidates(destination: str, destination_data: dict | None = None) -> list[dict]:
    dataset = destination_data or DESTINATION_DATA.get(destination)
    if not dataset:
        raise ValueError(f"Destination '{destination}' is not supported.")

    category_mapping = {
        "stays": "stay",
        "food": "food",
        "activities": "activity",
        "attractions": "attraction",
    }

    candidates: list[dict] = []
    for category_key, category_value in category_mapping.items():
        for item in dataset.get(category_key, []):
            item_copy = dict(item)
            item_copy["category"] = category_value
            item_copy.setdefault("reviews", list(DEFAULT_REVIEWS))
            item_copy.setdefault("crowd_density", DEFAULT_CROWD_DENSITY)
            item_copy.setdefault("best_time_to_visit", DEFAULT_BEST_TIME_TO_VISIT)
            item_copy.setdefault("popularity", DEFAULT_POPULARITY)
            candidates.append(item_copy)
    return candidates


def filter_candidates(candidates: list[dict], budget_cap_local: float) -> list[dict]:
    filtered: list[dict] = []
    for item in candidates:
        if item["price"] <= budget_cap_local * 1.25:
            filtered.append(item)
    return filtered


def enforce_total_budget(
    selected: list[dict],
    candidate_pool: list[dict],
    request: TripRequest,
    price_min_local: float | None,
    price_max_local: float | None,
) -> list[dict]:
    """Nudge the selected recommendations toward price_min_local/price_max_local as an
    overall trip-total target (not a per-item cap), by swapping in cheaper/pricier
    same-category alternatives from the full candidate pool, then trimming non-essential
    duplicate category picks if a lower target still can't be reached through swaps alone.
    price_min_local/price_max_local must already be converted into the destination's
    currency (see usd_to_local) — request.price_min/price_max are USD-denominated."""
    if price_min_local is None and price_max_local is None:
        return selected

    by_category: dict[str, list[dict]] = {}
    for item in candidate_pool:
        by_category.setdefault(item["category"], []).append(item)

    def total_of(items: list[dict]) -> float:
        return build_budget_breakdown(items, request).total

    def best_swap(items: list[dict], want_lower: bool, ceiling: float | None) -> tuple[int, dict] | None:
        current_ids = {entry["id"] for entry in items}
        current_total = total_of(items)
        best: tuple[int, dict, float] | None = None
        for index, item in enumerate(items):
            for option in by_category.get(item["category"], []):
                if option["id"] in current_ids:
                    continue
                if want_lower and option["price"] >= item["price"]:
                    continue
                if not want_lower and option["price"] <= item["price"]:
                    continue
                trial = list(items)
                trial[index] = option
                trial_total = total_of(trial)
                if ceiling is not None and trial_total > ceiling:
                    continue
                improves = trial_total < current_total if want_lower else trial_total > current_total
                if improves and (best is None or (trial_total < best[2] if want_lower else trial_total > best[2])):
                    best = (index, option, trial_total)
        return (best[0], best[1]) if best else None

    def costliest_extra_index(items: list[dict]) -> int | None:
        seen_categories: set[str] = set()
        extra_index, extra_price = None, -1.0
        for index, item in enumerate(items):
            if item["category"] in seen_categories:
                if item["price"] > extra_price:
                    extra_index, extra_price = index, item["price"]
            else:
                seen_categories.add(item["category"])
        return extra_index

    current = list(selected)

    if price_max_local is not None:
        while total_of(current) > price_max_local:
            swap = best_swap(current, want_lower=True, ceiling=None)
            if swap:
                index, option = swap
                current[index] = option
                continue
            drop_index = costliest_extra_index(current)
            if drop_index is None:
                break
            current.pop(drop_index)

    if price_min_local is not None:
        while total_of(current) < price_min_local:
            swap = best_swap(current, want_lower=False, ceiling=price_max_local)
            if not swap:
                break
            index, option = swap
            current[index] = option

    return current


def compute_preference_match(item: dict, preference_notes: str | None) -> float:
    if not preference_notes:
        return 0.0
    haystack = " ".join([item.get("title", ""), item.get("description", ""), " ".join(item.get("tags", []))]).casefold()
    tokens = {token for token in re.findall(r"[a-z0-9]+", preference_notes.casefold()) if len(token) > 2}
    if not tokens:
        return 0.0
    matches = sum(1 for token in tokens if token in haystack)
    return min(1.0, matches / len(tokens))


def score_item(item: dict, request: TripRequest, interest_tags: set[str], budget_cap_local: float) -> tuple[float, float, float, float, float, float, float]:
    rating_component = item["rating"] / 5.0
    budget_fit = max(0.0, 1.0 - (item["price"] / max(budget_cap_local, 1)) / 2.0)

    persona_weights = PERSONA_WEIGHTS[request.persona]
    item_tags = set(item["tags"])
    persona_overlap = item_tags & set(persona_weights.keys())
    persona_fit = sum(persona_weights[tag] for tag in persona_overlap) / max(sum(persona_weights.values()), 1.0)

    overlap = item_tags & interest_tags
    interest_match = len(overlap) / max(len(interest_tags), 1) if interest_tags else 0.0

    style_overlap = item_tags & STYLE_TAG_MAP[request.travel_style]
    style_fit = len(style_overlap) / max(len(STYLE_TAG_MAP[request.travel_style]), 1)

    preference_match = compute_preference_match(item, request.preference_notes)

    final_score = (
        0.30 * rating_component
        + 0.20 * budget_fit
        + 0.20 * persona_fit
        + 0.15 * interest_match
        + 0.15 * style_fit
        + 0.10 * preference_match
    )
    return rating_component, budget_fit, persona_fit, interest_match, style_fit, preference_match, final_score


def rank_candidates(candidates: list[dict], request: TripRequest, interest_tags: set[str], budget_cap_local: float) -> list[dict]:
    scored: list[dict] = []
    category_counts: dict[str, int] = {}
    for item in candidates:
        rating_component, budget_fit, persona_fit, interest_match, style_fit, preference_match, final_score = score_item(item, request, interest_tags, budget_cap_local)
        category_name = item["category"]
        category_counts[category_name] = category_counts.get(category_name, 0) + 1
        item_record = {
            **item,
            "rating_component": rating_component,
            "budget_fit": budget_fit,
            "persona_fit": persona_fit,
            "interest_match": interest_match,
            "style_fit": style_fit,
            "preference_match": preference_match,
            "score": final_score,
        }
        scored.append(item_record)

    scored.sort(key=lambda x: (x["score"], x["rating"], x["price"]), reverse=True)

    final: list[dict] = []
    seen_categories: set[str] = set()
    for item in scored:
        category = item["category"]
        if category in seen_categories and category_counts.get(category, 0) > 1:
            if len(final) < 6:
                final.append(item)
        else:
            final.append(item)
            seen_categories.add(category)
        if len(final) >= 6:
            break

    return final


def optimize_itinerary(request: TripRequest, ranked: list[dict]) -> list[dict]:
    style = STYLE_CONSTRAINTS[request.travel_style]
    activities = [item for item in ranked if item["category"] in {"activity", "attraction", "food"}]
    itinerary_days: list[dict] = []
    max_per_day = style["max_activities_per_day"]
    trip_days = max(1, min((request.end_date - request.start_date).days + 1, 14))
    activity_index = 0
    for day_index in range(1, trip_days + 1):
        remaining_days = trip_days - day_index + 1
        remaining_activities = len(activities) - activity_index
        activities_for_day = min(
            max_per_day,
            (remaining_activities + remaining_days - 1) // remaining_days,
        ) if remaining_activities else 0
        chosen = activities[activity_index:activity_index + activities_for_day]
        activity_index += len(chosen)
        if chosen:
            day_activities = [item["title"] for item in chosen]
            summary = f"A {style['pace']} day shaped for a {request.persona.lower()} traveller."
        elif day_index == 1:
            day_activities = ["Check in and settle in", "Take a short walk in the neighborhood"]
            summary = "Ease into the destination at a light pace."
        else:
            day_activities = ["Keep this day open for local discoveries"]
            summary = "Leave room for spontaneous discoveries and a slower local rhythm."
        itinerary_days.append({
            "day": day_index,
            "title": f"Day {day_index} in {request.destination}",
            "summary": summary,
            "activities": day_activities,
        })

    for index, place in enumerate(request.custom_places):
        day = itinerary_days[index % len(itinerary_days)]
        day["activities"].append(f"Your pick: {place}")

    return itinerary_days


def build_recommendation_payloads(recommendations: list[dict]) -> list[RecommendationItem]:
    payload: list[RecommendationItem] = []
    for item in recommendations:
        payload.append(
            RecommendationItem(
                id=item["id"],
                category=item["category"],
                title=item["title"],
                description=item["description"],
                price=float(item["price"]),
                tags=item.get("tags", []),
                rating=float(item["rating"]),
                location=item["location"],
                persona_fit=float(item.get("persona_fit", 0.0)),
                interest_match=float(item.get("interest_match", 0.0)),
                budget_fit=float(item.get("budget_fit", 0.0)),
                style_fit=float(item.get("style_fit", 0.0)),
                preference_match=float(item.get("preference_match", 0.0)),
                score=float(item.get("score", 0.0)),
                reason=(
                    f"Chosen for its {item['category']} role, "
                    f"{item.get('style_fit', 0.0):.0%} style fit, "
                    f"and {item.get('interest_match', 0.0):.0%} interest match."
                ),
                reviews=item.get("reviews", []),
                crowd_density=item.get("crowd_density", DEFAULT_CROWD_DENSITY),
                best_time_to_visit=item.get("best_time_to_visit", DEFAULT_BEST_TIME_TO_VISIT),
                popularity=item.get("popularity", DEFAULT_POPULARITY),
            )
        )
    return payload


def build_itinerary_payload(itinerary: list[dict]) -> list[ItineraryDay]:
    payload: list[ItineraryDay] = []
    for day in itinerary:
        payload.append(
            ItineraryDay(
                day=day["day"],
                title=day["title"],
                summary=day["summary"],
                activities=day["activities"],
            )
        )
    return payload


def build_budget_breakdown(recommendations: list[dict], request: TripRequest) -> BudgetBreakdown:
    trip_days = max(1, min((request.end_date - request.start_date).days + 1, 14))
    nights = max(1, trip_days - 1)
    travelers = request.travelers
    rooms = max(1, (travelers + 1) // 2)
    stay_total = sum(item["price"] for item in recommendations if item["category"] == "stay") * nights * rooms
    food_total = sum(item["price"] for item in recommendations if item["category"] == "food") * trip_days * travelers
    activity_total = sum(item["price"] for item in recommendations if item["category"] == "activity") * travelers
    attraction_total = sum(item["price"] for item in recommendations if item["category"] == "attraction") * travelers
    total = stay_total + food_total + activity_total + attraction_total
    return BudgetBreakdown(
        stay=stay_total,
        food=food_total,
        activities=activity_total + attraction_total,
        transport=total * 0.12,
        total=total * 1.12,
    )


def plan_trip(request: TripRequest, destination_data: dict | None = None) -> TripResponse:
    persona_weights, interest_tags, style_constraints = extract_features(request)
    candidates = generate_candidates(request.destination, destination_data)
    currency = (destination_data or DESTINATION_DATA[request.destination])["currency"]
    budget_cap_local = usd_to_local(BUDGET_THRESHOLDS[request.budget_level], currency)
    price_min_local = usd_to_local(request.price_min, currency) if request.price_min is not None else None
    price_max_local = usd_to_local(request.price_max, currency) if request.price_max is not None else None

    filtered = filter_candidates(candidates, budget_cap_local)
    if destination_data and len(filtered) < min(4, len(candidates)):
        filtered = candidates
    ranked = rank_candidates(filtered, request, interest_tags, budget_cap_local)
    itinerary_source = list(ranked)
    ranked = enforce_total_budget(ranked, candidates, request, price_min_local, price_max_local)

    for item in ranked:
        rating_component, budget_fit, persona_fit, interest_match, style_fit, preference_match, final_score = score_item(item, request, interest_tags, budget_cap_local)
        item["persona_fit"] = persona_fit
        item["interest_match"] = interest_match
        item["style_fit"] = style_fit
        item["budget_fit"] = budget_fit
        item["preference_match"] = preference_match
        item["score"] = final_score

    itinerary = optimize_itinerary(request, itinerary_source)
    recommendation_payload = build_recommendation_payloads(ranked)
    itinerary_payload = build_itinerary_payload(itinerary)
    budget_breakdown = build_budget_breakdown(ranked, request)

    return TripResponse(
        destination=request.destination,
        persona=request.persona,
        budget_level=request.budget_level,
        travel_style=request.travel_style,
        interests=request.interests,
        travelers=request.travelers,
        trip_days=max(1, min((request.end_date - request.start_date).days + 1, 14)),
        currency=currency,
        narrative=f"{request.persona} travellers to {request.destination} are best served by a {request.travel_style.lower()} itinerary that balances {', '.join(request.interests)} with memorable local experiences.",
        recommendations=recommendation_payload,
        itinerary=itinerary_payload,
        budget_breakdown=budget_breakdown,
        custom_places=request.custom_places,
    )
