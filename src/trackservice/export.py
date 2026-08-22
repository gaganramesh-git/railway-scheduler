"""Serialise a solved scenario into the JSON the dashboard reads.

The dashboard is a static file with the JSON embedded, so this is the contract
between solver and UI. Times are emitted in BOTH ticks (for layout maths) and
wall-clock strings (for humans), so the front end never re-derives clock time.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from .alternatives import Alternative
from .explain import Explanation
from .types import Schedule, Scenario, format_clock, ticks_to_hours


def scenario_payload(scenario: Scenario) -> dict:
    return {
        "nights": scenario.nights,
        "seed": scenario.seed,
        "sections": [
            {"id": s.id, "name": s.name, "traffic": s.traffic_density}
            for s in scenario.sections
        ],
        "windows": [
            {
                "section": w.section_id,
                "night": w.night,
                "start": w.start,
                "end": w.end,
                "start_clock": format_clock(w.start),
                "end_clock": format_clock(w.end),
            }
            for w in scenario.windows
        ],
        "requests": [
            {
                "id": r.id,
                "title": r.title,
                "section": r.section_id,
                "duration": r.duration,
                "duration_h": ticks_to_hours(r.duration),
                "priority": r.priority.value,
                "crew": r.crew.value,
                "crew_size": r.crew_size,
                "equipment": r.equipment.value,
                "earliest_night": r.earliest_night,
                "latest_night": r.latest_night,
                "emergency": r.is_emergency,
            }
            for r in scenario.requests
        ],
        "pool": {
            "crew": {k.value: v for k, v in scenario.pool.crew.items()},
            "equipment": {k.value: v for k, v in scenario.pool.equipment.items()},
            "crew_shift": scenario.pool.crew_shift,
        },
    }


def schedule_payload(schedule: Schedule) -> dict:
    return {
        "status": schedule.status,
        "objective": schedule.objective,
        "solve_seconds": schedule.solve_seconds,
        "proven_optimal": schedule.proven_optimal,
        "assignments": [
            {
                "id": a.request_id,
                "night": a.night,
                "start": a.start,
                "end": a.end,
                "start_clock": format_clock(a.start),
                "end_clock": format_clock(a.end),
            }
            for a in schedule.assignments
        ],
        "unscheduled": schedule.unscheduled,
    }


def metrics(scenario: Scenario, schedule: Schedule) -> dict:
    """The numbers to quote on stage."""
    total = len(scenario.requests)
    placed = len(schedule.assignments)
    booked = sum(a.duration for a in schedule.assignments)
    window_ticks = sum(w.length for w in scenario.windows)
    return {
        "total_requests": total,
        "scheduled": placed,
        "scheduled_pct": round(100 * placed / total, 1) if total else 0.0,
        "window_utilisation_pct": round(100 * booked / window_ticks, 1) if window_ticks else 0.0,
        "priority_weight": schedule.objective,
        "solve_seconds": schedule.solve_seconds,
        "proven_optimal": schedule.proven_optimal,
    }


def build_report(
    scenario: Scenario,
    optimal: Schedule,
    greedy: Schedule,
    explanations: list[Explanation],
    alternatives: list[Alternative],
    emergency: dict | None = None,
) -> dict:
    return {
        "scenario": scenario_payload(scenario),
        "optimal": schedule_payload(optimal),
        "greedy": schedule_payload(greedy),
        "metrics": {
            "optimal": metrics(scenario, optimal),
            "greedy": metrics(scenario, greedy),
        },
        "explanations": [asdict(e) for e in explanations],
        "alternatives": [asdict(a) for a in alternatives],
        "emergency": emergency,
    }


def write_json(report: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
