import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "wandr.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                destination TEXT NOT NULL,
                narrative TEXT NOT NULL,
                recommendations TEXT NOT NULL,
                itinerary TEXT NOT NULL,
                budget_breakdown TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def save_trip(trip_payload: dict) -> int:
    init_db()
    with get_connection() as conn:
        values = (
            trip_payload.get("destination", "Unknown"),
            trip_payload.get("narrative", ""),
            str(trip_payload.get("recommendations", [])),
            str(trip_payload.get("itinerary", [])),
            str(trip_payload.get("budget_breakdown", {})),
        )
        existing = conn.execute(
            """
            SELECT id FROM trips
            WHERE destination = ? AND narrative = ? AND recommendations = ?
              AND itinerary = ? AND budget_breakdown = ?
            ORDER BY id ASC
            LIMIT 1
            """,
            values,
        ).fetchone()
        if existing:
            return int(existing["id"])

        cursor = conn.execute(
            """
            INSERT INTO trips (destination, narrative, recommendations, itinerary, budget_breakdown)
            VALUES (?, ?, ?, ?, ?)
            """,
            values,
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_saved_trip(trip_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, destination, narrative, recommendations, itinerary, budget_breakdown FROM trips WHERE id = ?",
            (trip_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "destination": row["destination"],
        "narrative": row["narrative"],
        "recommendations": row["recommendations"],
        "itinerary": row["itinerary"],
        "budget_breakdown": row["budget_breakdown"],
    }


def list_saved_trips() -> list[dict]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, destination, narrative, recommendations, itinerary, budget_breakdown FROM trips ORDER BY id DESC"
        ).fetchall()
    return [
        {
            "id": row["id"],
            "destination": row["destination"],
            "narrative": row["narrative"],
            "recommendations": row["recommendations"],
            "itinerary": row["itinerary"],
            "budget_breakdown": row["budget_breakdown"],
        }
        for row in rows
    ]


def delete_saved_trip(trip_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
        conn.commit()
    return cursor.rowcount > 0
