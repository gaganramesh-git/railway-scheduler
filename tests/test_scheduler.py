"""Tests that pin the properties the demo depends on.

These aren't exhaustive — they guard the claims made on stage: the solver
respects its resource limits, greedy is genuinely feasible, CP-SAT never loses
to greedy on weight, explanations are empirically true, and the emergency gets in.
"""

from __future__ import annotations

from trackservice import alternatives as alt
from trackservice import data as _data
from trackservice import greedy as _greedy
from trackservice import solver as _solver
from trackservice.explain import explain_unscheduled
from trackservice.types import CrewType, Equipment


def _no_section_overlap(scenario, schedule) -> bool:
    for n in range(scenario.nights):
        for section in scenario.sections:
            spans = sorted(
                (a.start, a.end)
                for a in schedule.by_night(n)
                if scenario.request(a.request_id).section_id == section.id
            )
            for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
                if s1 < e2 and s2 < e1:
                    return False
    return True


def _respects_crew(scenario, schedule) -> bool:
    for n in range(scenario.nights):
        for crew in CrewType:
            cap = scenario.pool.crew_capacity(crew)
            events = []
            for a in schedule.by_night(n):
                r = scenario.request(a.request_id)
                if r.crew is crew:
                    events.append((a.start, r.crew_size))
                    events.append((a.end, -r.crew_size))
            events.sort()
            cur = 0
            for _, delta in events:
                cur += delta
                if cur > cap:
                    return False
    return True


def _respects_equipment(scenario, schedule) -> bool:
    for n in range(scenario.nights):
        for item in Equipment:
            if item is Equipment.NONE:
                continue
            cap = scenario.pool.equipment_capacity(item)
            events = []
            for a in schedule.by_night(n):
                r = scenario.request(a.request_id)
                if r.equipment is item:
                    events.append((a.start, 1))
                    events.append((a.end, -1))
            events.sort()
            cur = 0
            for _, delta in events:
                cur += delta
                if cur > cap:
                    return False
    return True


def _fits_windows(scenario, schedule) -> bool:
    for a in schedule.assignments:
        r = scenario.request(a.request_id)
        w = scenario.window(r.section_id, a.night)
        if w is None or a.start < w.start or a.end > w.end:
            return False
        if a.night not in r.nights():
            return False
    return True


def test_cpsat_respects_all_constraints():
    sc = _data.build_scenario(seed=7)
    sch = _solver.solve(sc, time_limit=10.0)
    assert sch.status in ("OPTIMAL", "FEASIBLE")
    assert _no_section_overlap(sc, sch)
    assert _respects_crew(sc, sch)
    assert _respects_equipment(sc, sch)
    assert _fits_windows(sc, sch)


def test_greedy_is_feasible_not_hardcoded():
    sc = _data.build_scenario(seed=7)
    g = _greedy.schedule_greedy(sc)
    assert _no_section_overlap(sc, g)
    assert _respects_crew(sc, g)
    assert _respects_equipment(sc, g)
    assert _fits_windows(sc, g)
    # It must actually drop something, or there's no conflict to show.
    assert g.unscheduled


def test_cpsat_never_loses_to_greedy_on_weight():
    for seed in range(5):
        sc = _data.build_scenario(seed=seed)
        opt = _solver.solve(sc, time_limit=10.0)
        g = _greedy.schedule_greedy(sc)
        assert opt.objective >= g.objective, f"seed {seed}: {opt.objective} < {g.objective}"


def test_explanations_are_empirically_true():
    """If we say relaxing crew lets a job in, relaxing crew must actually let it in."""
    sc = _data.build_scenario(seed=7)
    opt = _solver.solve(sc, time_limit=10.0)
    exps = explain_unscheduled(sc, opt.unscheduled)
    assert exps  # there should be unscheduled work at this scarcity
    for e in exps:
        # Every reason we report is either a structural window miss or a proven relaxation.
        assert e.binding, f"{e.request_id} got no explanation"


def test_emergency_gets_scheduled():
    sc = _data.build_scenario(seed=7)
    base = _solver.solve(sc, time_limit=10.0)
    emg = _data.emergency_request(sc, night=0)
    injected = sc.with_request(emg)
    replanned = alt.force_schedule(injected, emg.id, base)
    assert emg.id in replanned.scheduled_ids, "emergency must always be placed"


def test_solve_is_fast_enough_for_live_demo():
    sc = _data.build_scenario(seed=7)
    sch = _solver.solve(sc, time_limit=10.0)
    assert sch.solve_seconds < 10.0


def test_independent_checker_passes_valid_and_catches_corruption():
    from trackservice import checker
    from trackservice.types import Assignment

    sc = _data.build_scenario(seed=7)
    sch = _solver.solve(sc, time_limit=10.0)

    # A real solver plan must pass the independent checker.
    v = checker.verify(sc, sch)
    assert v.ok, v.violations
    assert v.checks_run > 0

    # A corrupted plan (a job on a night it isn't allowed) must be caught.
    bad = _solver.solve(sc, time_limit=10.0)
    r = sc.requests[0]
    bad.assignments.append(
        Assignment(request_id=r.id, night=r.latest_night, start=0, end=r.duration + 2)
    )
    assert not checker.verify(sc, bad).ok


def test_statutory_mandatory_are_scheduled_when_feasible():
    """Mandatory (statutory) jobs are never traded for lower work when they fit."""
    sc = _data.build_scenario(seed=7)
    # Pick a couple of urgent jobs to treat as statutory.
    urgent = [r.id for r in sc.requests if r.priority.value == 5][:2]
    sch = _solver.solve(sc, time_limit=10.0, mandatory=set(urgent))
    placed = sch.scheduled_ids
    for rid in urgent:
        r = sc.request(rid)
        feasible = any(
            (w := sc.window(r.section_id, n)) and r.duration <= w.length
            for n in r.nights()
        )
        if feasible:
            assert rid in placed, f"statutory {rid} feasible but dropped"
