"""CP-SAT scheduler for maintenance blocks.

The model, in one breath: each request gets one optional interval per night it's
allowed to run on; a boolean says whether that (request, night) is chosen; a
request runs on at most one night; chosen intervals may not overlap on a section,
may not exceed crew or equipment capacity, and must respect crew duty hours. We
maximise the priority weight actually scheduled.

Everything is in half-hour ticks (see types.py). Solve time is capped so the
service can re-solve live; pass `warm_start` from a previous schedule to make an
incremental re-solve land in well under a second.
"""

from __future__ import annotations

import time

from ortools.sat.python import cp_model

from .types import (
    Assignment,
    CrewType,
    Equipment,
    Schedule,
    Scenario,
)


def solve(
    scenario: Scenario,
    time_limit: float = 10.0,
    warm_start: Schedule | None = None,
) -> Schedule:
    model = cp_model.CpModel()
    reqs = scenario.requests

    # --- decision variables -------------------------------------------------
    # present[(r, n)]  : this request runs on night n
    # start[(r, n)]    : its start tick on night n (meaningful only if present)
    # interval[(r, n)] : an OPTIONAL interval, active iff present — the object the
    #                    no-overlap and cumulative constraints actually reason over
    present: dict[tuple[str, int], cp_model.IntVar] = {}
    starts: dict[tuple[str, int], cp_model.IntVar] = {}
    intervals: dict[tuple[str, int], cp_model.IntervalVar] = {}

    for r in reqs:
        for n in r.nights():
            window = scenario.window(r.section_id, n)
            if window is None or r.duration > window.length:
                continue  # no block, or the job can't fit inside it: not a candidate
            key = (r.id, n)
            present[key] = model.NewBoolVar(f"present_{r.id}_{n}")
            starts[key] = model.NewIntVar(
                window.start, window.end - r.duration, f"start_{r.id}_{n}"
            )
            intervals[key] = model.NewOptionalIntervalVar(
                starts[key], r.duration, starts[key] + r.duration,
                present[key], f"iv_{r.id}_{n}",
            )

    # --- each request runs at most once -------------------------------------
    scheduled: dict[str, cp_model.IntVar] = {}
    for r in reqs:
        options = [present[(r.id, n)] for n in r.nights() if (r.id, n) in present]
        is_sched = model.NewBoolVar(f"sched_{r.id}")
        if options:
            model.Add(sum(options) == is_sched)
        else:
            model.Add(is_sched == 0)  # infeasible everywhere; can never be placed
        scheduled[r.id] = is_sched

    # --- no two blocks overlap on the same section, same night --------------
    for section in scenario.sections:
        for n in range(scenario.nights):
            same = [
                intervals[(r.id, n)]
                for r in reqs
                if r.section_id == section.id and (r.id, n) in intervals
            ]
            if len(same) > 1:
                model.AddNoOverlap(same)

    # --- crew capacity: a cumulative resource, per crew type, per night -----
    # Height = gangs used; capacity = gangs available. This is what silently
    # breaks if durations aren't in the same units as the window — see types.py.
    for crew in CrewType:
        cap = scenario.pool.crew_capacity(crew)
        for n in range(scenario.nights):
            ivs, demands = [], []
            for r in reqs:
                if r.crew is crew and (r.id, n) in intervals:
                    ivs.append(intervals[(r.id, n)])
                    demands.append(r.crew_size)
            if ivs:
                model.AddCumulative(ivs, demands, cap)

    # --- equipment capacity: same shape, per machine type, per night --------
    for item in Equipment:
        if item is Equipment.NONE:
            continue
        cap = scenario.pool.equipment_capacity(item)
        for n in range(scenario.nights):
            ivs = [
                intervals[(r.id, n)]
                for r in reqs
                if r.equipment is item and (r.id, n) in intervals
            ]
            if ivs:
                model.AddCumulative(ivs, [1] * len(ivs), cap)

    # --- crew duty hours: total booked crew-ticks per type per night --------
    # One gang may not exceed a shift, so the pool caps total booked crew-time.
    for crew in CrewType:
        budget = scenario.pool.crew_capacity(crew) * scenario.pool.crew_shift
        for n in range(scenario.nights):
            load = [
                present[(r.id, n)] * (r.duration * r.crew_size)
                for r in reqs
                if r.crew is crew and (r.id, n) in present
            ]
            if load:
                model.Add(sum(load) <= budget)

    # --- objective: maximise scheduled priority weight ----------------------
    model.Maximize(sum(scheduled[r.id] * r.priority.value for r in reqs))

    # --- warm start: hint the previous placements to speed incremental solves
    if warm_start is not None:
        for a in warm_start.assignments:
            key = (a.request_id, a.night)
            if key in present:
                model.AddHint(present[key], 1)
                model.AddHint(starts[key], a.start)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8

    t0 = time.perf_counter()
    status = solver.Solve(model)
    elapsed = time.perf_counter() - t0

    return _extract(scenario, solver, status, present, starts, elapsed)


def _extract(scenario, solver, status, present, starts, elapsed) -> Schedule:
    result = Schedule(
        status=solver.StatusName(status),
        solve_seconds=round(elapsed, 3),
        proven_optimal=(status == cp_model.OPTIMAL),
    )
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result.unscheduled = [r.id for r in scenario.requests]
        return result

    for r in scenario.requests:
        placed = False
        for n in r.nights():
            key = (r.id, n)
            if key in present and solver.Value(present[key]) == 1:
                s = solver.Value(starts[key])
                result.assignments.append(
                    Assignment(request_id=r.id, night=n, start=s, end=s + r.duration)
                )
                placed = True
                break
        if not placed:
            result.unscheduled.append(r.id)

    result.objective = int(solver.ObjectiveValue())
    return result
