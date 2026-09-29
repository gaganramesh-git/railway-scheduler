"""The chartering optimiser (CP-SAT), the reactive spot baseline, and an
independent feasibility checker — the same three-part pattern the block planner
uses: optimise, compare against what the operator does today, and verify.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from ortools.sat.python import cp_model

from .data import candidate_voyages
from .model import Assignment, CharterPlan, Scenario


def _feasible_voyages(scenario, voyages):
    """parcel id -> voyages that can legally carry it (same lane, fits, on time)."""
    by = {p.id: [] for p in scenario.parcels}
    for p in scenario.parcels:
        transit = scenario.origin(p.origin_id).transit_weeks
        for v in voyages:
            if (v.origin_id == p.origin_id and v.port_id == p.port_id
                    and v.capacity_t >= p.volume_t
                    and v.depart_week + transit <= p.required_by_week):
                by[p.id].append(v)
    return by


def optimize(scenario: Scenario, time_limit: float = 10.0) -> CharterPlan:
    voyages = candidate_voyages(scenario)
    vmap = {v.id: v for v in voyages}
    by = _feasible_voyages(scenario, voyages)

    model = cp_model.CpModel()
    use = {v.id: model.NewBoolVar(f"use_{v.id}") for v in voyages}
    assign, served = {}, {}

    for p in scenario.parcels:
        avars = []
        for v in by[p.id]:
            a = model.NewBoolVar(f"a_{p.id}_{v.id}")
            assign[(p.id, v.id)] = a
            model.Add(a <= use[v.id])          # can't load a voyage we don't charter
            avars.append(a)
        s = model.NewBoolVar(f"s_{p.id}")
        served[p.id] = s
        model.Add(sum(avars) == s) if avars else model.Add(s == 0)

    # A chartered voyage can't be over-loaded.
    for v in voyages:
        terms = [assign[(p.id, v.id)] * p.volume_t
                 for p in scenario.parcels if (p.id, v.id) in assign]
        if terms:
            model.Add(sum(terms) <= v.capacity_t)

    # Objective: freight cost + a large penalty for leaving a parcel unserved
    # (weighted by priority) + a small idle-capacity charge to right-size vessels.
    IDLE = 2  # $/tonne of unused capacity on a chartered voyage
    UNSERVED = 10_000_000
    cost_terms = [int(vmap[vid].cost) * use[vid] for vid in use]
    idle_terms = [int(vmap[vid].capacity_t) * IDLE * use[vid] for vid in use]
    served_vol = [p.volume_t * IDLE * served[p.id] for p in scenario.parcels]
    unserved_pen = [UNSERVED * p.priority * (1 - served[p.id]) for p in scenario.parcels]
    model.Minimize(sum(cost_terms) + sum(idle_terms) - sum(served_vol) + sum(unserved_pen))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8
    t0 = time.perf_counter()
    status = solver.Solve(model)
    elapsed = round(time.perf_counter() - t0, 3)

    plan = CharterPlan(status=solver.StatusName(status), solve_seconds=elapsed,
                       proven_optimal=(status == cp_model.OPTIMAL))
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        plan.unserved = [p.id for p in scenario.parcels]
        return plan

    used_cost = 0.0
    used = set()
    for p in scenario.parcels:
        if solver.Value(served[p.id]) == 0:
            plan.unserved.append(p.id)
            continue
        for v in by[p.id]:
            if solver.Value(assign[(p.id, v.id)]) == 1:
                transit = scenario.origin(p.origin_id).transit_weeks
                plan.assignments.append(Assignment(
                    parcel_id=p.id, voyage_id=v.id, vessel_id=v.vessel_id,
                    origin_id=v.origin_id, port_id=v.port_id, depart_week=v.depart_week,
                    arrive_week=v.depart_week + transit, volume_t=p.volume_t))
                used.add(v.id)
                break
    used_cost = sum(vmap[vid].cost for vid in used)
    plan.total_cost = round(used_cost, 0)
    plan.voyages_used = len(used)
    return plan


def spot_baseline(scenario: Scenario) -> CharterPlan:
    """What procurement does today: charter each parcel on its own, on the smallest
    vessel that fits, as late as possible (reactive spot at the deadline week). No
    consolidation, no timing play."""
    t0 = time.perf_counter()
    plan = CharterPlan(status="SPOT_REACTIVE")
    total = 0.0
    for p in scenario.parcels:
        port = scenario.port(p.port_id)
        transit = scenario.origin(p.origin_id).transit_weeks
        depart = max(0, p.required_by_week - transit)  # as late as possible
        # smallest vessel that fits the port and the parcel
        options = [v for v in scenario.vessels
                   if v.draft_m <= port.max_draft_m and v.loa_m <= port.max_loa_m
                   and v.dwt >= p.volume_t]
        if not options:
            plan.unserved.append(p.id)
            continue
        v = min(options, key=lambda v: v.dwt)
        cost = v.base_rate_per_t * v.dwt * scenario.rate(v.id, depart)
        total += cost
        plan.assignments.append(Assignment(
            parcel_id=p.id, voyage_id=f"SPOT-{p.id}", vessel_id=v.id,
            origin_id=p.origin_id, port_id=p.port_id, depart_week=depart,
            arrive_week=depart + transit, volume_t=p.volume_t))
    plan.total_cost = round(total, 0)
    plan.voyages_used = len(plan.assignments)   # one charter per parcel
    plan.solve_seconds = round(time.perf_counter() - t0, 3)
    return plan


@dataclass
class Verdict:
    ok: bool
    checks_run: int
    violations: list


def verify(scenario: Scenario, plan: CharterPlan) -> Verdict:
    """Independent re-check of a finished plan — separate logic from the solver, so
    it catches solver bugs rather than repeating them."""
    violations, checks = [], 0
    load: dict[str, int] = {}
    for a in plan.assignments:
        p = scenario.parcel(a.parcel_id)
        port = scenario.port(a.port_id)
        v = scenario.vessel(a.vessel_id)
        checks += 3
        if v.draft_m > port.max_draft_m:
            violations.append(f"{a.parcel_id}: {v.name} draft {v.draft_m}m > {port.name} {port.max_draft_m}m")
        if v.loa_m > port.max_loa_m:
            violations.append(f"{a.parcel_id}: {v.name} LOA exceeds {port.name}")
        if a.arrive_week > p.required_by_week:
            violations.append(f"{a.parcel_id}: arrives wk{a.arrive_week} > required wk{p.required_by_week}")
        load[a.voyage_id] = load.get(a.voyage_id, 0) + a.volume_t
    for vid, tot in load.items():
        checks += 1
        cap = next((scenario.vessel(a.vessel_id).dwt for a in plan.assignments if a.voyage_id == vid), 0)
        if tot > cap:
            violations.append(f"{vid}: loaded {tot}t > capacity {cap}t")
    # every parcel appears at most once
    seen = [a.parcel_id for a in plan.assignments]
    checks += 1
    if len(seen) != len(set(seen)):
        violations.append("a parcel is assigned more than once")
    return Verdict(ok=not violations, checks_run=checks, violations=violations)
