from fastapi import APIRouter, HTTPException

from app.schemas.trip import TripRequest, TripResponse
from app.services.ai_personalization import generate_personalization
from app.services.destination_resolver import resolve_destination
from app.services.persistence import delete_saved_trip, get_saved_trip, list_saved_trips, save_trip
from app.services.trip_engine import plan_trip

router = APIRouter(prefix="/trips", tags=["trips"])


@router.post("/plan", response_model=TripResponse)
def generate_trip(request: TripRequest) -> TripResponse:
    try:
        brief = request.brief or request.destination
        if request.agent_decides:
            brief = (
                f"Trip brief: {brief}. "
                f"Destination requested: {request.destination}. "
                f"Travel dates: {request.start_date} to {request.end_date}. "
                f"Travelers: {request.travelers}. "
                f"persona={request.persona}. "
                f"budget={request.budget_level}. "
                f"style={request.travel_style}. "
                f"interests={', '.join(request.interests)}. "
                "Use all of this client-side information to decide destination, persona, budget, travel style, and interests."
            )
        resolution = resolve_destination(brief, prefer_agent=request.agent_decides)
        updates = {"destination": resolution.canonical_name}
        if request.agent_decides and resolution.source == "agent":
            decision = resolution.decision
            if decision:
                updates.update({
                    "persona": decision.persona or request.persona,
                    "budget_level": decision.budget_level or request.budget_level,
                    "travel_style": decision.travel_style or request.travel_style,
                    "interests": decision.interests or request.interests,
                })
        resolved_request = request.model_copy(update=updates)
        trip = plan_trip(resolved_request, destination_data=resolution.dataset)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    api_key = None
    narrative = generate_personalization(
        destination=resolved_request.destination,
        persona=resolved_request.persona,
        interests=resolved_request.interests,
        top_recommendations=[item.title for item in trip.recommendations[:2]],
        api_key=api_key,
    )
    trip.narrative = narrative
    trip.resolution_source = resolution.source
    trip.resolution_confidence = resolution.confidence
    trip.agent_rationale = resolution.rationale
    return trip


@router.post("/save")
def save_trip_route(payload: dict) -> dict:
    saved_id = save_trip(payload)
    return {"saved": True, "id": saved_id}


@router.get("/saved")
def list_trips() -> list[dict]:
    return list_saved_trips()


@router.get("/saved/{trip_id}")
def get_trip(trip_id: int) -> dict:
    trip = get_saved_trip(trip_id)
    if not trip:
        return {"error": "Trip not found"}
    return trip


@router.delete("/saved/{trip_id}")
def delete_trip(trip_id: int) -> dict:
    deleted = delete_saved_trip(trip_id)
    return {"deleted": deleted, "id": trip_id}
