"""
Seed 8 weeks of realistic weekly history per district so the
/dashboard/[district] page and /dashboard/reports forecast page can render.

For each district in the water_risk_dataset, the latest row gives us a
"current" anchor. We step backwards 8 Sundays with a small random walk so
the values are plausible but not identical. We only seed if the table is
empty for that district -- repeated calls don't overwrite fresh entries
(upsert) but the seeder only writes when no rows exist, so existing
operational data is never overwritten.

Run automatically on FastAPI startup via app.main's lifespan.
"""
from __future__ import annotations

import csv
import logging
import os
import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config import DATA_DIR
from app.history_models import WeeklyHistory

logger = logging.getLogger(__name__)

_NEEDED_WEEKS = 8
_SUNDAY = 6  # weekday() == 6 is Sunday

# Mirror of weather_service.DISTRICT_ALIASES. Both legacy (CSV-side) and
# modern (frontend-side) spellings need to resolve to the same weekly_history
# rows, otherwise /history/weekly/{Cumilla} returns empty when the user
# switches districts on the dashboard. The CSV uses the modern spelling for
# Jashore and Chattogram but the legacy spelling for Comilla and Bogra.
_DISTRICT_ALIASES = {
    "cumilla": "comilla",
    "bogura": "bogra",
    "jashore": "jashore",
    "chattogram": "chattogram",
    # legacy aliases for OpenWeatherMap or user input
    "jessore": "jashore",
    "chittagong": "chattogram",
}


def _latest_conditions() -> dict[str, dict[str, float]]:
    """Return the most recent observed environmental reading from the dataset.

    For every row's CSV name, ALSO store the same record under any modern
    / preferred alias (Cumilla, Bogura, Jashore, Chattogram). This means
    a /history/weekly/{Cumilla} lookup hits the same rows as
    /history/weekly/{Comilla}, regardless of which spelling the dashboard
    sent. Fixes the "disease breakdown ashse na" bug for Cumilla/Bogura
    where the weather service returned null district conditions and
    the frontend's diseaseParams stayed null, so breakdownMutation.mutate
    never fired.
    """
    path = os.path.join(os.path.dirname(os.path.dirname(DATA_DIR)), "data", "water_risk_dataset.csv.xls")
    if not os.path.exists(path):
        path = os.path.join(DATA_DIR, "water_risk_dataset.csv.xls")
    if not os.path.exists(path):
        return {}
    latest: dict[str, dict[str, float]] = {}
    with open(path, newline="", encoding="utf-8") as fp:
        for row in csv.DictReader(fp):
            district = (row.get("district") or "").strip().lower()
            if not district:
                continue
            row_date = row.get("date") or ""
            anchor = {
                "date": row_date,
                "rainfall_mm": float(row["rainfall_mm"]),
                "river_level_m": float(row["river_level_m"]),
                "population_density": float(row["population_density"]),
                "sanitation_score": float(row["sanitation_score"]),
                "water_quality_index": float(row["water_quality_index"]),
            }
            if district not in latest or row_date > latest[district]["date"]:
                latest[district] = anchor
            # Mirror under every modern/preferred alias so callers using the
            # newer district name (e.g. "cumilla") find the same row.
            for modern, legacy in _DISTRICT_ALIASES.items():
                if legacy == district and modern != district:
                    if modern not in latest or row_date > latest[modern]["date"]:
                        latest[modern] = anchor
    return latest


def _recent_sunday(today: date) -> date:
    """Return the most recent past Sunday (or today if today is Sunday)."""
    days_back = (today.weekday() - _SUNDAY) % 7
    return today - timedelta(days=days_back)


def seed_weekly_history_if_empty(db: Session) -> int:
    """For every district with no history rows yet, insert 8 weeks of
    synthetic-but-plausible observations. Returns the number of rows added."""
    conditions = _latest_conditions()
    if not conditions:
        logger.warning("seed_weekly_history_if_empty: dataset not found; skipping seed.")
        return 0

    rng = random.Random(42)  # deterministic so the same district always seeds the same shape
    last_sunday = _recent_sunday(date.today())
    weeks_back = [_last_sunday_minus(i) for i in range(_NEEDED_WEEKS)]  # oldest -> newest

    added = 0
    for district_lower, anchor in conditions.items():
        existing = db.query(WeeklyHistory).filter(WeeklyHistory.district == district_lower).count()
        if existing >= _NEEDED_WEEKS:
            continue  # operational data exists; never overwrite

        rainfall_anchor = max(0.0, anchor["rainfall_mm"])
        temp_anchor = 25.0  # district page derives temperature from live weather; here we just need a stable number for LSTM scale
        flood_anchor = max(0.0, anchor["river_level_m"] * 100.0)  # convert river-level m -> flood-depth cm, roughly
        # IMPORTANT: sanitation_score is on a 0..1 scale in /predict/forecast and
        # /predict/disease (matching how the LSTM and outbreak models were trained
        # in Colab), but the water_risk_dataset reports it 0..100. Normalise here
        # so downstream calls don't 422.
        sanitation_anchor = max(0.0, min(1.0, anchor["sanitation_score"] / 100.0))
        baseline_cases = max(2.0, flood_anchor / 6.0)

        # Build oldest -> newest with mild random walk.
        rain = rainfall_anchor
        flood = flood_anchor
        sanitation = sanitation_anchor
        cases = baseline_cases
        for i, week_end in enumerate(weeks_back):
            rain = max(0.0, rain + rng.uniform(-6, 6))
            flood = max(0.0, flood + rng.uniform(-8, 8))
            sanitation = max(0.0, min(1.0, sanitation + rng.uniform(-0.02, 0.02)))
            cases = max(1.0, cases + rng.uniform(-3, 4))

            db.add(WeeklyHistory(
                district=district_lower,
                week_ending=week_end,
                weekly_cases=round(cases, 2),
                rainfall_mm=round(rain, 2),
                temperature_c=round(temp_anchor + rng.uniform(-1.5, 1.5), 2),
                flood_depth_cm=round(flood, 2),
                sanitation_score=round(sanitation, 4),
            ))
            added += 1

    if added:
        db.commit()
        logger.info("Seeded %d weekly_history rows.", added)
    return added


def _last_sunday_minus(n: int) -> date:
    today = date.today()
    days_back = (today.weekday() - _SUNDAY) % 7
    last_sunday = today - timedelta(days=days_back)
    return last_sunday - timedelta(weeks=n)