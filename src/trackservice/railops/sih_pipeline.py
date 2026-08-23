"""End-to-end SIH26027 run on the real corridor, with the statutory guarantee.

Ties together: real-corridor BDMS scenario → CP-SAT with statutory (T0) jobs as
hard-dominant → greedy baseline → empirical explanations → proposed alternatives
→ an IMR emergency injection. Produces the same report shape the dashboard reads,
enriched with BDMS metadata (department, reason code, tier) and the headline
statutory metric: deadlines met by us vs by first-come-first-served.
"""

from __future__ import annotations

from dataclasses import replace

from .. import alternatives as alt
from .. import export as _export
from .. import greedy as _greedy
from .. import solver as _solver
from ..explain import explain_unscheduled
from ..types import Equipment, Priority, Request, hours_to_ticks
from . import generator as _gen


def _mandatory(meta) -> set[str]:
    return {rid for rid, m in meta.items() if m.tier == 0}


def build_standard_scenario(seed: int = 3, nights: int = 30, from_feeds: bool = False):
    """The canonical scenario for the block plan, with the COA goods forecast folded
    into block availability. `from_feeds=True` reads the TMS/SMMS/TDMS/COA export
    files on disk instead of the synthetic generator — same planner either way."""
    if from_feeds:
        from . import integrations as _intg
        return _intg.build_scenario_from_feeds()
    goods = _gen.synth_goods_forecast(seed)
    return _gen.build_scenario(seed=seed, nights=nights, goods_forecast=goods)


def run(seed: int = 3, nights: int = 30, custom_emergency=None, apply_ids=None,
        analyze: bool = True, from_feeds: bool = False) -> dict:
    """Build the plan report.

    `analyze` controls the expensive relax-and-re-solve analysis (per-job
    explanations and proposed alternatives). It's on for the cached base plan, but
    off for live actions (apply / emergency), where the user only needs the new
    schedule and what it bumped — keeping those actions snappy on a long horizon.
    """
    scenario, meta = build_standard_scenario(seed=seed, nights=nights, from_feeds=from_feeds)

    # Fold in demands committed from the depot screen and pin them so a raised
    # task always lands on the graph.
    from . import demands as _demands
    scenario, meta, committed_ids = _demands.apply_to(scenario, meta, scenario.nights)

    t0 = _mandatory(meta)

    # The base plan always honours statutory (T0) work; it's the report's "optimal".
    optimal = _solver.solve(scenario, time_limit=10.0, mandatory=t0 | set(committed_ids))
    greedy = _greedy.schedule_greedy(scenario)

    # Explaining is relax-and-re-solve per job — the dominant cost on a long
    # horizon — so it's skipped for live actions and only run for the base plan.
    if analyze:
        ranked_unscheduled = sorted(
            optimal.unscheduled,
            key=lambda rid: scenario.request(rid).priority.value,
            reverse=True,
        )
        explanations = explain_unscheduled(scenario, ranked_unscheduled[:10])
        alternatives = [alt.propose_for(scenario, optimal, rid)
                        for rid in ranked_unscheduled[:8]]
    else:
        explanations, alternatives = [], []

    if apply_ids:
        emergency = _run_apply(scenario, meta, optimal, t0, list(apply_ids))
    else:
        emergency = _run_imr_emergency(scenario, optimal, t0, custom=custom_emergency)

    report = _export.build_report(
        scenario, optimal, greedy, explanations, alternatives, emergency
    )
    _enrich(report, meta)
    report["statutory"] = _statutory_metrics(scenario, meta, optimal, greedy)

    from . import shadow as _shadow

    proposals, saved = _shadow.detect(scenario, optimal, meta)
    report["shadows"] = {
        "corridors_saved": saved,
        "proposals": [p.__dict__ for p in proposals],
    }

    from .. import checker as _checker

    ver = _checker.verify(scenario, optimal, mandatory=t0)
    report["verification"] = {
        "ok": ver.ok,
        "checks_run": ver.checks_run,
        "violations": ver.violations,
    }
    report["corridor"] = {
        "name": "Kanpur – Mughal Sarai (New Delhi–Howrah main line)",
        "source": "Indian Railways public timetable (data.gov.in / datameet)",
    }

    # COA goods-trains forecast made visible: split each section's effective traffic
    # back into timetable passenger paths + forecast freight paths, so the plan shows
    # what the goods forecast contributes to block availability.
    from .timetable import load_corridor as _lc
    pax = {s.id: s.trains_per_day for s in _lc()}
    by_section = []
    for s in report["scenario"]["sections"]:
        p = pax.get(s["id"], s["traffic"])
        g = max(0, s["traffic"] - p)
        s["passenger"] = p
        s["goods"] = g
        by_section.append({"id": s["id"], "name": s["name"],
                           "passenger": p, "goods": g, "effective": s["traffic"]})
    report["goods_forecast"] = {
        "source": "COA goods-trains forecast",
        "total_goods_paths": sum(x["goods"] for x in by_section),
        "by_section": by_section,
        "feeds": ["tms_defects.csv", "smms_defects.csv", "tdms_defects.csv",
                  "coa_block_availability.csv", "coa_goods_forecast.csv"],
    }

    # Derived KPIs the planner view shows.
    slots = {(scenario.request(a.request_id).section_id, a.night) for a in optimal.assignments}
    report["blocks_demanded"] = len(slots)
    report["speed_restriction_hours"] = _speed_restriction_hours(scenario, meta, optimal)

    from . import audit as _audit

    report["audit"] = _audit.report_entries(report)
    return report


def _speed_restriction_hours(scenario, meta, schedule) -> int:
    """Traffic-weighted speed-restriction hours still on the network — the ongoing
    unavailability from urgent defects left open after the plan."""
    from statistics import mean
    traffic = {s.id: s.traffic_density for s in scenario.sections}
    avg = mean(traffic.values())
    placed = schedule.scheduled_ids
    total = 0.0
    for r in scenario.requests:
        m = meta.get(r.id)
        if r.id not in placed and m and m.tier <= 1:
            total += 10.0 * (traffic[r.section_id] / avg)
    return round(total)


def _run_imr_emergency(scenario, baseline, t0, custom=None) -> dict:
    """A rail fracture with IMR classification, detected after planning closed —
    a statutory job with a hard 3-day clock that must be absorbed. `custom` is an
    optional judge-authored Request from the live form."""
    busiest = max(scenario.sections, key=lambda s: s.traffic_density)
    emg = custom if custom is not None else Request(
        id="EMG-IMR-01",
        title="IMR rail fracture (detected)",
        section_id=busiest.id,
        duration=hours_to_ticks(2.5),
        priority=Priority.URGENT,
        crew=scenario.request(next(iter(t0))).crew if t0 else scenario.requests[0].crew,
        crew_size=2,
        equipment=Equipment.ROAD_RAILER,
        earliest_night=0,
        latest_night=min(2, scenario.nights - 1),  # ~3-day IMR clock
        is_emergency=True,
    )
    injected = scenario.with_request(emg)
    reopt = alt.force_schedule(injected, emg.id, baseline)
    bumped = sorted(baseline.scheduled_ids - reopt.scheduled_ids)
    true_weight = sum(
        injected.request(a.request_id).priority.value for a in reopt.assignments
    )
    payload = _export.schedule_payload(reopt)
    payload["objective"] = true_weight
    metrics = _export.metrics(injected, reopt)
    metrics["priority_weight"] = true_weight
    return {
        "kind": "emergency",
        "request": {"id": emg.id, "title": emg.title, "section": emg.section_id, "night": emg.earliest_night},
        "scenario": _export.scenario_payload(injected),
        "schedule": payload,
        "metrics": metrics,
        "bumped": bumped,
        "weight_before": baseline.objective,
        "weight_after": true_weight,
    }


def _run_apply(scenario, meta, base, t0, apply_ids) -> dict:
    """Pin the requested jobs on top of statutory work, re-solve, report the diff."""
    pinned = _solver.solve(scenario, time_limit=10.0, mandatory=t0 | set(apply_ids))
    scheduled_now = pinned.scheduled_ids
    pinned_scheduled = [rid for rid in apply_ids if rid in scheduled_now]
    pinned_failed = [rid for rid in apply_ids if rid not in scheduled_now]
    bumped = sorted(base.scheduled_ids - scheduled_now)
    true_weight = pinned.objective
    last = apply_ids[-1]
    r = scenario.request(last)
    a = pinned.assignment(last)
    payload = _export.schedule_payload(pinned)
    payload["objective"] = true_weight
    metrics = _export.metrics(scenario, pinned)
    metrics["priority_weight"] = true_weight
    return {
        "kind": "applied",
        "request": {"id": r.id, "title": r.title, "section": r.section_id,
                    "night": a.night if a else r.earliest_night},
        "pinned": list(apply_ids),
        "pinned_scheduled": pinned_scheduled,
        "pinned_failed": pinned_failed,
        "scenario": _export.scenario_payload(scenario),
        "schedule": payload,
        "metrics": metrics,
        "bumped": bumped,
        "weight_before": base.objective,
        "weight_after": true_weight,
    }


def _enrich(report: dict, meta) -> None:
    """Attach BDMS fields (department, reason code, tier) onto every request in
    the report so the dashboard can colour and badge them."""
    def tag(reqs):
        for r in reqs:
            m = meta.get(r["id"])
            if m:
                r["department"] = m.department
                r["reason_code"] = m.reason_code
                r["tier"] = m.tier
                r["statutory"] = m.tier == 0
                r["committed"] = m.committed
    tag(report["scenario"]["requests"])
    if report.get("emergency"):
        tag(report["emergency"]["scenario"]["requests"])


def _statutory_metrics(scenario, meta, optimal, greedy) -> dict:
    t0 = _mandatory(meta)
    opt_sched = optimal.scheduled_ids
    gr_sched = greedy.scheduled_ids
    opt_met = len(t0 & opt_sched)
    gr_met = len(t0 & gr_sched)
    return {
        "total": len(t0),
        "cpsat_met": opt_met,
        "greedy_met": gr_met,
        "cpsat_missed": sorted(t0 - opt_sched),
        "greedy_missed": sorted(t0 - gr_sched),
    }


if __name__ == "__main__":
    rep = run()
    s = rep["statutory"]
    om, gm = rep["metrics"]["optimal"], rep["metrics"]["greedy"]
    print(f"Corridor: {rep['corridor']['name']}")
    print(f"Source:   {rep['corridor']['source']}\n")
    print(f"Statutory (T0) deadlines met:  CP-SAT {s['cpsat_met']}/{s['total']}   "
          f"greedy/FIFO {s['greedy_met']}/{s['total']}")
    if s["greedy_missed"]:
        print(f"   → FIFO misses statutory jobs: {', '.join(s['greedy_missed'])}")
    print(f"Total scheduled:  CP-SAT {om['scheduled']}/{om['total_requests']}  "
          f"(weight {om['priority_weight']})   greedy {gm['scheduled']}/{gm['total_requests']} "
          f"(weight {gm['priority_weight']})")
    print(f"Solve: {om['solve_seconds']}s  {'OPTIMAL (proven)' if om['proven_optimal'] else om['status']}")
    e = rep["emergency"]
    print(f"\nEmergency {e['request']['title']} on {e['request']['section']}: "
          f"re-solved {e['schedule']['solve_seconds']}s, bumped {e['bumped'] or 'nothing'}, "
          f"weight {e['weight_before']}→{e['weight_after']}")
