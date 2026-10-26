from app.schemas.trip import TripRequest
from app.services.trip_engine import compute_preference_match, plan_trip


def build_request(**overrides):
    base = {
        "destination": "Kyoto",
        "start_date": "2026-10-12",
        "end_date": "2026-10-18",
        "travelers": 2,
        "persona": "Couple",
        "budget_level": "Midrange",
        "travel_style": "Cultural",
        "interests": ["Food", "History"],
    }
    base.update(overrides)
    return TripRequest(**base)


def test_different_persona_changes_recommendation_order():
    couple = plan_trip(build_request(persona="Couple"))
    solo = plan_trip(build_request(persona="Solo"))

    assert couple.recommendations != solo.recommendations
    assert couple.itinerary != solo.itinerary


def test_different_destination_changes_candidate_pool():
    kyoto = plan_trip(build_request(destination="Kyoto"))
    lisbon = plan_trip(build_request(destination="Lisbon"))

    assert kyoto.destination == "Kyoto"
    assert lisbon.destination == "Lisbon"
    assert kyoto.recommendations != lisbon.recommendations


def test_different_interests_change_top_rankings():
    food_history = plan_trip(build_request(interests=["Food", "History"]))
    nightlife_shopping = plan_trip(build_request(interests=["Nightlife", "Shopping"]))

    assert food_history.recommendations != nightlife_shopping.recommendations


def test_budget_breakdown_uses_actual_recommendation_prices():
    trip = plan_trip(build_request())
    stay = sum(item.price for item in trip.recommendations if item.category == "stay") * 6
    food = sum(item.price for item in trip.recommendations if item.category == "food") * 7 * 2
    activities = sum(item.price for item in trip.recommendations if item.category in {"activity", "attraction"}) * 2
    expected_before_transport = stay + food + activities
    assert abs(trip.budget_breakdown.total - expected_before_transport * 1.12) < 1


def test_traveler_count_changes_budget_and_response_metadata():
    couple = plan_trip(build_request(travelers=2))
    group = plan_trip(build_request(travelers=6))

    assert couple.travelers == 2
    assert group.travelers == 6
    assert group.budget_breakdown.total > couple.budget_breakdown.total


def test_trip_duration_changes_itinerary_metadata_and_budget():
    short_trip = plan_trip(build_request(end_date="2026-10-13"))
    long_trip = plan_trip(build_request(end_date="2026-10-26"))

    assert short_trip.trip_days == 2
    assert long_trip.trip_days == 15 or long_trip.trip_days == 14
    assert long_trip.budget_breakdown.total > short_trip.budget_breakdown.total


def test_itinerary_covers_every_requested_trip_day():
    trip = plan_trip(build_request())

    assert len(trip.itinerary) == trip.trip_days == 7
    assert [day.day for day in trip.itinerary] == list(range(1, 8))
    assert all(day.activities for day in trip.itinerary)


def test_itinerary_does_not_repeat_recommendations():
    trip = plan_trip(build_request(end_date="2026-10-16"))
    activities = [activity for day in trip.itinerary for activity in day.activities]

    assert len(activities) == len(set(activities))


def test_travel_style_changes_recommendation_scores():
    cultural = plan_trip(build_request(travel_style="Cultural"))
    foodie = plan_trip(build_request(travel_style="Foodie"))

    assert [item.id for item in cultural.recommendations] != [item.id for item in foodie.recommendations]
    assert [item.style_fit for item in cultural.recommendations] != [item.style_fit for item in foodie.recommendations]


def test_itinerary_density_changes_by_travel_style():
    relaxed = plan_trip(build_request(travel_style="Relaxed"))
    adventurous = plan_trip(build_request(travel_style="Adventurous"))

    assert len(relaxed.itinerary) >= len(adventurous.itinerary)
    assert len(relaxed.itinerary[0].activities) <= len(adventurous.itinerary[0].activities)


def test_price_max_lowers_trip_total_toward_target():
    default_trip = plan_trip(build_request())
    reduced_target = default_trip.budget_breakdown.total * 0.7
    constrained_trip = plan_trip(build_request(price_max=reduced_target))

    assert constrained_trip.budget_breakdown.total < default_trip.budget_breakdown.total


def test_price_min_raises_trip_total_toward_target():
    default_trip = plan_trip(build_request())
    raised_target = default_trip.budget_breakdown.total * 1.5
    boosted_trip = plan_trip(build_request(price_min=raised_target))

    assert boosted_trip.budget_breakdown.total > default_trip.budget_breakdown.total


def test_price_range_unset_matches_default_budget_behavior():
    default_trip = plan_trip(build_request())
    explicit_none_trip = plan_trip(build_request(price_min=None, price_max=None))

    assert [item.id for item in default_trip.recommendations] == [item.id for item in explicit_none_trip.recommendations]
    assert default_trip.budget_breakdown == explicit_none_trip.budget_breakdown


def test_compute_preference_match_scores_keyword_overlap():
    item = {"title": "Fushimi Inari Sunrise Walk", "description": "Torii gates before the crowds.", "tags": ["adventure", "nature"]}

    assert compute_preference_match(item, None) == 0.0
    assert compute_preference_match(item, "") == 0.0
    assert compute_preference_match(item, "I want to see the Fushimi Inari torii gates") > 0.0


def test_preference_notes_boost_recommendation_score():
    baseline = plan_trip(build_request())
    boosted = plan_trip(build_request(preference_notes="I really want to visit Kinkaku-ji gold temple"))

    baseline_item = next(item for item in baseline.recommendations if item.id == "kyoto-attraction-1")
    boosted_item = next(item for item in boosted.recommendations if item.id == "kyoto-attraction-1")

    assert boosted_item.preference_match > 0.0
    assert boosted_item.score > baseline_item.score


def test_custom_places_are_woven_into_itinerary_and_echoed_back():
    trip = plan_trip(build_request(custom_places=["Nijo Castle", "Local ramen shop"]))

    assert trip.custom_places == ["Nijo Castle", "Local ramen shop"]
    all_activities = [activity for day in trip.itinerary for activity in day.activities]
    assert "Your pick: Nijo Castle" in all_activities
    assert "Your pick: Local ramen shop" in all_activities


def test_tight_budget_target_does_not_starve_itinerary_of_activities():
    default_trip = plan_trip(build_request(end_date="2026-10-16"))
    tight_trip = plan_trip(build_request(end_date="2026-10-16", price_max=default_trip.budget_breakdown.total * 0.7))

    filler_days = [day for day in tight_trip.itinerary if day.activities == ["Keep this day open for local discoveries"]]
    assert len(filler_days) <= 1


def test_recommendations_carry_reviews_crowd_and_timing_details():
    trip = plan_trip(build_request())

    assert all(item.reviews for item in trip.recommendations)
    assert all(item.crowd_density in {"Low", "Medium", "High"} for item in trip.recommendations)
    assert all(item.best_time_to_visit for item in trip.recommendations)
    assert all(item.popularity in {"Hidden gem", "Popular"} for item in trip.recommendations)
