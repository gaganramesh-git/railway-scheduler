"""End-to-end chartering run: optimise, compare with reactive spot, verify, and
assemble one JSON report the dashboard reads. Plus a multi-scenario evaluator.
"""

from __future__ import annotations

from statistics import mean, pstdev

from . import data as _data
from .model import Scenario
from .optimizer import optimize, spot_baseline, verify


def _voyage_view(scenario: Scenario, plan) -> list[dict]:
    groups: dict[str, dict] = {}
    for a in plan.assignments:
        g = groups.setdefault(a.voyage_id, {
            "voyage_id": a.voyage_id, "vessel": scenario.vessel(a.vessel_id).name,
            "vessel_id": a.vessel_id, "origin": scenario.origin(a.origin_id).name,
            "port": scenario.port(a.port_id).name, "port_id": a.port_id,
            "depart_week": a.depart_week, "arrive_week": a.arrive_week,
            "capacity_t": scenario.vessel(a.vessel_id).dwt, "parcels": [], "load_t": 0,
        })
        g["parcels"].append(a.parcel_id)
        g["load_t"] += a.volume_t
    for g in groups.values():
        g["utilisation_pct"] = round(100 * g["load_t"] / g["capacity_t"], 1)
        g["shared"] = len(g["parcels"]) > 1
    return sorted(groups.values(), key=lambda g: (g["depart_week"], g["port_id"]))


def _metrics(scenario, plan, spot) -> dict:
    total = len(scenario.parcels)
    cap_used = sum(scenario.vessel(a.vessel_id).dwt for a in
                   {a.voyage_id: a for a in plan.assignments}.values())
    vol = sum(a.volume_t for a in plan.assignments)
    saving = spot.total_cost - plan.total_cost
    return {
        "ours_cost": plan.total_cost,
        "spot_cost": spot.total_cost,
        "cost_saved": round(saving, 0),
        "cost_saved_pct": round(100 * saving / spot.total_cost, 1) if spot.total_cost else 0,
        "ours_voyages": plan.voyages_used,
        "spot_voyages": spot.voyages_used,
        "voyages_saved": spot.voyages_used - plan.voyages_used,
        "ours_served": len(plan.served_ids),
        "spot_served": len(spot.served_ids),
        "total_parcels": total,
        "on_time_pct": round(100 * len(plan.served_ids) / total, 1) if total else 0,
        "utilisation_pct": round(100 * vol / cap_used, 1) if cap_used else 0,
        "parcels_per_voyage": round(len(plan.served_ids) / plan.voyages_used, 2) if plan.voyages_used else 0,
    }


def run(seed: int = 3, weeks: int = 12, from_feeds: bool = False) -> dict:
    if from_feeds:
        from . import feeds as _feeds
        scenario = _feeds.build_scenario_from_feeds()
    else:
        scenario = _data.build_scenario(seed=seed, weeks=weeks)

    # Fold in operator edits: manually-raised cargo (pinned) and cancellations.
    from . import requests_store as _store
    scenario, manual_ids, cancelled = _store.apply_to(scenario)
    weeks = scenario.weeks

    plan = optimize(scenario, time_limit=10.0)
    spot = spot_baseline(scenario)
    ver = verify(scenario, plan)

    # Market-entry forecast per vessel class, to the end of the horizon.
    forecast = [_data.forecast_entry(scenario, v.id, weeks - 1) for v in scenario.vessels]
    for f in forecast:
        f["vessel_name"] = scenario.vessel(f["vessel"]).name

    report = {
        "problem": "SIH26006 — Intelligent Freight Forecasting & Optimised Vessel Chartering",
        "org": "Ministry of Steel",
        "scenario": {
            "weeks": weeks,
            "ports": [{"id": p.id, "name": p.name, "max_draft_m": p.max_draft_m,
                       "handling_tpd": p.handling_rate_tpd} for p in scenario.ports],
            "vessels": [{"id": v.id, "name": v.name, "dwt": v.dwt, "draft_m": v.draft_m,
                         "base_rate_per_t": v.base_rate_per_t} for v in scenario.vessels],
            "origins": [{"id": o.id, "name": o.name, "transit_weeks": o.transit_weeks}
                        for o in scenario.origins],
            "parcels": [{"id": p.id, "commodity": p.commodity, "origin": p.origin_id,
                         "port": p.port_id, "volume_t": p.volume_t,
                         "required_by_week": p.required_by_week, "priority": p.priority,
                         "manual": p.manual}
                        for p in scenario.parcels],
            "rate_index": {f"{k[0]}|{k[1]}": val for k, val in scenario.rate_index.items()},
        },
        "plan": {
            "status": plan.status, "proven_optimal": plan.proven_optimal,
            "solve_seconds": plan.solve_seconds, "total_cost": plan.total_cost,
            "voyages_used": plan.voyages_used, "unserved": plan.unserved,
            "voyages": _voyage_view(scenario, plan),
        },
        "baseline": {"total_cost": spot.total_cost, "voyages_used": spot.voyages_used,
                     "unserved": spot.unserved},
        "metrics": _metrics(scenario, plan, spot),
        "forecast": forecast,
        "verification": {"ok": ver.ok, "checks_run": ver.checks_run,
                         "violations": ver.violations},
        "market": _data.BALTIC,
        "manual_ids": manual_ids,
        "cancelled": cancelled,
    }
    # flag voyages that carry a manually-raised parcel, for the dashboard badge
    manual_set = set(manual_ids)
    for v in report["plan"]["voyages"]:
        v["manual"] = any(pid in manual_set for pid in v["parcels"])

    from . import audit as _audit
    report["audit"] = _audit.report_entries(report)
    return report


def run_eval(seeds: int = 20, weeks: int = 12) -> dict:
    rows = []
    for s in range(seeds):
        sc = _data.build_scenario(seed=s, weeks=weeks)
        plan = optimize(sc, time_limit=10.0)
        spot = spot_baseline(sc)
        m = _metrics(sc, plan, spot)
        m["verified"] = verify(sc, plan).ok
        m["solve_seconds"] = plan.solve_seconds
        rows.append(m)

    def agg(k):
        vals = [r[k] for r in rows]
        return round(mean(vals), 2), round(pstdev(vals) if len(vals) > 1 else 0.0, 2)

    return {
        "seeds": seeds,
        "cost_saved_pct": agg("cost_saved_pct"),
        "voyages_saved": agg("voyages_saved"),
        "on_time_pct": agg("on_time_pct"),
        "utilisation_pct": agg("utilisation_pct"),
        "parcels_per_voyage": agg("parcels_per_voyage"),
        "solve_seconds": agg("solve_seconds"),
        "all_verified": all(r["verified"] for r in rows),
    }
