"""First-come-first-served baseline — the 'before' picture.

A genuine greedy scheduler, not a hardcoded set of conflicts. It walks requests
in submission order and drops each into the first feasible slot it finds, with no
reordering and no backtracking. Its failures are real feasibility failures: change
the data or the order and the dropped set changes with it.

This exists to be beaten. The gap between what this drops and what CP-SAT drops is
the whole argument — greedy loses high-priority jobs to bad luck of ordering;
the optimiser never does.
"""

from __future__ import annotations

import time

from .types import Assignment, CrewType, Equipment, Schedule, Scenario


def schedule_greedy(scenario: Scenario) -> Schedule:
    t0 = time.perf_counter()
    result = Schedule(status="GREEDY_FCFS")

    # Live occupancy, rebuilt as we place. Keyed by night.
    section_busy: dict[int, list[tuple[str, int, int]]] = {}  # (section_id, start, end)
    crew_ticks: dict[tuple[int, CrewType], int] = {}
    crew_conc: dict[int, list[tuple[CrewType, int, int, int]]] = {}  # (crew, start, end, size)
    equip_conc: dict[int, list[tuple[Equipment, int, int]]] = {}     # (equip, start, end)

    for r in scenario.requests:  # submission order — no sorting, that's the point
        placed = _place(scenario, r, section_busy, crew_ticks, crew_conc, equip_conc)
        if placed is not None:
            result.assignments.append(placed)
        else:
            result.unscheduled.append(r.id)

    result.objective = sum(
        scenario.request(a.request_id).priority.value for a in result.assignments
    )
    result.solve_seconds = round(time.perf_counter() - t0, 3)
    return result


def _place(scenario, r, section_busy, crew_ticks, crew_conc, equip_conc):
    for n in r.nights():
        window = scenario.window(r.section_id, n)
        if window is None or r.duration > window.length:
            continue

        # Try every tick offset; take the first that clears all resource checks.
        for start in range(window.start, window.end - r.duration + 1):
            end = start + r.duration
            if _fits(scenario, r, n, start, end, section_busy, crew_ticks, crew_conc, equip_conc):
                section_busy.setdefault(n, []).append((r.section_id, start, end))
                key = (n, r.crew)
                crew_ticks[key] = crew_ticks.get(key, 0) + r.duration * r.crew_size
                crew_conc.setdefault(n, []).append((r.crew, start, end, r.crew_size))
                if r.equipment is not Equipment.NONE:
                    equip_conc.setdefault(n, []).append((r.equipment, start, end))
                return Assignment(request_id=r.id, night=n, start=start, end=end)
    return None


def _fits(scenario, r, n, start, end, section_busy, crew_ticks, crew_conc, equip_conc) -> bool:
    # Section: no overlap with anything already on this section tonight.
    for sid, s, e in section_busy.get(n, []):
        if sid == r.section_id and start < e and s < end:
            return False

    # Crew duty hours: would this bust the shift budget for its type?
    budget = scenario.pool.crew_capacity(r.crew) * scenario.pool.crew_shift
    if crew_ticks.get((n, r.crew), 0) + r.duration * r.crew_size > budget:
        return False

    # Crew concurrency: gangs of this type in use during [start,end) + this job.
    cap = scenario.pool.crew_capacity(r.crew)
    for t in range(start, end):
        used = r.crew_size + sum(
            size for c, s, e, size in crew_conc.get(n, []) if c is r.crew and s <= t < e
        )
        if used > cap:
            return False

    # Equipment concurrency.
    if r.equipment is not Equipment.NONE:
        ecap = scenario.pool.equipment_capacity(r.equipment)
        for t in range(start, end):
            used = 1 + sum(
                1 for eq, s, e in equip_conc.get(n, []) if eq is r.equipment and s <= t < e
            )
            if used > ecap:
                return False
    return True
