import os


def generate_personalization(destination: str, persona: str, interests: list[str], top_recommendations: list[str], api_key: str | None = None) -> str:
    if not api_key:
        interest_text = ", ".join(interests) if interests else "local experiences"
        top_text = ", ".join(top_recommendations[:2]) if top_recommendations else "signature highlights"
        return (
            f"This {persona.lower()} trip to {destination} is shaped around {interest_text}, with {top_text} bringing the route to life in a way that feels personal, paced, and easy to enjoy."
        )

    return (
        f"A {persona.lower()} itinerary for {destination} built around {', '.join(interests)} and anchored by {', '.join(top_recommendations[:2])}. The journey balances local rhythm, comfort, and memorable detail to match your travel style."
    )
