"""Tests for the SIH26006 vessel-chartering optimiser — guard the claims the demo
depends on: the plan is feasible, cheaper than reactive spot, and on time."""

from __future__ import annotations

from trackservice.marine import data as _data
from trackservice.marine import optimizer as _opt
from trackservice.marine import pipeline as _pl


def test_plan_verifies_and_is_feasible():
    sc = _data.build_scenario(seed=3, weeks=12)
    plan = _opt.optimize(sc, time_limit=10.0)
    v = _opt.verify(sc, plan)
    assert v.ok, v.violations
    # no voyage over capacity, every assigned vessel fits its port
    for a in plan.assignments:
        port = sc.port(a.port_id)
        vessel = sc.vessel(a.vessel_id)
        assert vessel.draft_m <= port.max_draft_m
        assert a.arrive_week <= sc.parcel(a.parcel_id).required_by_week


def test_optimiser_beats_or_matches_spot():
    sc = _data.build_scenario(seed=3, weeks=12)
    plan = _opt.optimize(sc, time_limit=10.0)
    spot = _opt.spot_baseline(sc)
    # never more expensive than booking everything reactively at the deadline
    assert plan.total_cost <= spot.total_cost
    # and it uses no more charters than spot (consolidation + right-sizing)
    assert plan.voyages_used <= spot.voyages_used


def test_all_feasible_cargo_served():
    sc = _data.build_scenario(seed=3, weeks=12)
    plan = _opt.optimize(sc, time_limit=10.0)
    # every parcel in this scenario is constructed feasibly, so none should drop
    assert plan.unserved == []


def test_report_shape():
    r = _pl.run(seed=1, weeks=12)
    for key in ("metrics", "plan", "baseline", "forecast", "verification", "scenario"):
        assert key in r
    assert r["metrics"]["cost_saved_pct"] >= 0
    assert r["verification"]["ok"]


def test_eval_cost_saving_positive_on_average():
    r = _pl.run_eval(seeds=8, weeks=12)
    assert r["all_verified"]
    assert r["cost_saved_pct"][0] > 0        # saves money on average
    assert r["on_time_pct"][0] == 100.0      # all feasible cargo delivered on time
