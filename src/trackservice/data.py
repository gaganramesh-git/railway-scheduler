"""Synthetic — but plausible — railway maintenance scenario.

Every number here is authored in hours and converted once, at the boundary, via
`hours_to_ticks`. Downstream code never sees hours again.

The scarcity is deliberate. Crew and machine pools are set tight relative to
demand so that conflicts arise from genuine resource contention, not from nights
being too short. A scenario where everything fits proves nothing on stage.
"""

from __future__ import annotations

import random

from .types import (
    CrewType,
    Equipment,
    Priority,
    Request,
    ResourcePool,
    Scenario,
    Section,
    Window,
    hours_to_ticks,
)

# Real maintenance activity templates: (title, crew, crew_size, equipment, duration_hours, priority)
_ROUTINE_TEMPLATES = [
    ("Track tamping", CrewType.PWAY, 1, Equipment.TAMPER, 3.0, Priority.IMPORTANT),
    ("Ballast cleaning", CrewType.PWAY, 1, Equipment.BALLAST_CLEANER, 4.0, Priority.IMPORTANT),
    ("Rail grinding", CrewType.PWAY, 1, Equipment.RAIL_GRINDER, 3.0, Priority.ROUTINE),
    ("Signal testing", CrewType.SIGNAL, 1, Equipment.NONE, 2.0, Priority.ROUTINE),
    ("Interlocking check", CrewType.SIGNAL, 1, Equipment.NONE, 2.5, Priority.IMPORTANT),
    ("OHE tension adjustment", CrewType.OHE, 1, Equipment.TOWER_WAGON, 2.5, Priority.ROUTINE),
    ("OHE insulator replacement", CrewType.OHE, 1, Equipment.TOWER_WAGON, 3.0, Priority.IMPORTANT),
    ("Bridge girder inspection", CrewType.BRIDGE, 1, Equipment.ROAD_RAILER, 2.0, Priority.ROUTINE),
    ("Fishplate greasing", CrewType.PWAY, 1, Equipment.NONE, 1.5, Priority.ROUTINE),
    ("Points lubrication", CrewType.SIGNAL, 1, Equipment.NONE, 1.5, Priority.ROUTINE),
]

# Urgent, safety-driven work. Short deadlines, high weight, refuses to wait.
_URGENT_TEMPLATES = [
    ("Rail fracture repair", CrewType.PWAY, 2, Equipment.ROAD_RAILER, 2.5, Priority.URGENT),
    ("Points failure rectification", CrewType.SIGNAL, 1, Equipment.NONE, 2.0, Priority.URGENT),
    ("OHE breakdown repair", CrewType.OHE, 2, Equipment.TOWER_WAGON, 3.0, Priority.URGENT),
    ("Weld defect grinding", CrewType.PWAY, 1, Equipment.RAIL_GRINDER, 2.0, Priority.URGENT),
]

_SECTIONS = [
    Section("SEC-A", "Junction North Throat", traffic_density=48),
    Section("SEC-B", "Up Main — Km 12–18", traffic_density=36),
    Section("SEC-C", "Down Main — Km 12–18", traffic_density=34),
    Section("SEC-D", "Loop Line East", traffic_density=12),
    Section("SEC-E", "Ghat Section — Km 40–47", traffic_density=22),
    Section("SEC-F", "Yard Reception Lines", traffic_density=8),
    Section("SEC-G", "Bridge Approach — Km 55", traffic_density=18),
    Section("SEC-H", "Suburban Corridor — Km 3–9", traffic_density=52),
]


def build_scenario(seed: int = 7, n_requests: int = 40, nights: int = 5) -> Scenario:
    rng = random.Random(seed)
    sections = list(_SECTIONS)

    windows = _build_windows(rng, sections, nights)

    # A tight pool. These caps, not the clock, are what force the hard choices.
    pool = ResourcePool(
        crew={
            CrewType.PWAY: 2,
            CrewType.SIGNAL: 1,
            CrewType.OHE: 1,
            CrewType.BRIDGE: 1,
        },
        equipment={
            Equipment.TAMPER: 1,
            Equipment.BALLAST_CLEANER: 1,
            Equipment.RAIL_GRINDER: 1,
            Equipment.TOWER_WAGON: 1,
            Equipment.ROAD_RAILER: 1,
        },
        crew_shift=hours_to_ticks(5.0),  # a gang works at most 5h a night
    )

    requests = _build_requests(rng, sections, nights, n_requests)
    return Scenario(
        sections=sections,
        windows=windows,
        requests=requests,
        pool=pool,
        nights=nights,
        seed=seed,
    )


def _build_windows(
    rng: random.Random, sections: list[Section], nights: int
) -> list[Window]:
    """Nightly blocks of 4–6h. High-traffic sections lose some nights entirely."""
    windows: list[Window] = []
    for section in sections:
        for night in range(nights):
            # Busy corridors can't always be handed over for engineering work.
            blackout_chance = 0.30 if section.traffic_density > 40 else 0.12
            if rng.random() < blackout_chance:
                continue
            length_h = rng.choice([4.0, 4.5, 5.0, 5.5, 6.0])
            start = 0  # every window opens at 22:00 (tick 0)
            windows.append(
                Window(
                    section_id=section.id,
                    night=night,
                    start=start,
                    end=start + hours_to_ticks(length_h),
                )
            )
    return windows


def _build_requests(
    rng: random.Random,
    sections: list[Section],
    nights: int,
    n_requests: int,
) -> list[Request]:
    requests: list[Request] = []
    n_urgent = max(4, n_requests // 8)

    for i in range(n_requests):
        idx = i + 1
        is_urgent = i < n_urgent
        if is_urgent:
            title, crew, crew_size, equip, dur_h, prio = rng.choice(_URGENT_TEMPLATES)
            earliest = rng.randint(0, max(0, nights - 2))
            latest = min(nights - 1, earliest + rng.randint(0, 1))  # tight deadline
        else:
            title, crew, crew_size, equip, dur_h, prio = rng.choice(_ROUTINE_TEMPLATES)
            earliest = rng.randint(0, nights - 1)
            latest = min(nights - 1, earliest + rng.randint(1, nights - 1))

        section = rng.choice(sections)
        requests.append(
            Request(
                id=f"WR-{idx:03d}",
                title=title,
                section_id=section.id,
                duration=hours_to_ticks(dur_h),
                priority=prio,
                crew=crew,
                crew_size=crew_size,
                equipment=equip,
                earliest_night=earliest,
                latest_night=latest,
            )
        )
    return requests


def emergency_request(scenario: Scenario, night: int = 0) -> Request:
    """A rail fracture reported after planning closed — the 'propose alternatives' trigger.

    It targets the busiest section that has a window on `night`, so placing it
    genuinely forces something else out.
    """
    candidates = [
        s for s in scenario.sections if scenario.window(s.id, night) is not None
    ]
    section = max(candidates, key=lambda s: s.traffic_density)
    n = sum(1 for r in scenario.requests if r.is_emergency) + 1
    return Request(
        id=f"EMG-{n:03d}",
        title="EMERGENCY rail fracture repair",
        section_id=section.id,
        duration=hours_to_ticks(2.5),
        priority=Priority.URGENT,
        crew=CrewType.PWAY,
        crew_size=2,
        equipment=Equipment.ROAD_RAILER,
        earliest_night=night,
        latest_night=night,
        is_emergency=True,
    )
