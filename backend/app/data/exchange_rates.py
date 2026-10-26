# Static, indicative exchange rates (units of each currency per 1 USD).
# Not live-updated — refresh these values manually if they drift too far from
# real rates. Covers the catalog's destination currencies (JPY, EUR, INR, MYR),
# common display-currency choices (USD, GBP), and a few currencies the AI
# planning agent frequently resolves to for non-catalog destinations. Also used
# to convert the USD-denominated budget tiers/targets (see trip_engine.py) into
# whatever currency a given destination actually prices in. A currency missing
# from this table falls back to a 1:1 USD rate (see trip_engine.usd_to_local) —
# add it here instead of leaving that fallback to silently under/overshoot.
EXCHANGE_RATES_USD: dict[str, float] = {
    "USD": 1.0,
    "JPY": 149.5,
    "EUR": 0.92,
    "INR": 83.0,
    "MYR": 4.7,
    "GBP": 0.79,
    "AUD": 1.52,
    "CAD": 1.36,
    "MAD": 10.0,
    "IDR": 15800.0,
    "NGN": 1550.0,
    "ISK": 138.0,
    "THB": 35.0,
    "VND": 25400.0,
    "AED": 3.67,
    "MXN": 18.0,
}
