from fastapi import APIRouter

from app.data.exchange_rates import EXCHANGE_RATES_USD
from app.services.trip_engine import BUDGET_THRESHOLDS

router = APIRouter(prefix="/currency", tags=["currency"])


@router.get("/rates")
def get_rates() -> dict:
    return {"base": "USD", "rates": EXCHANGE_RATES_USD}


@router.get("/budget-thresholds")
def get_budget_thresholds() -> dict:
    return BUDGET_THRESHOLDS
