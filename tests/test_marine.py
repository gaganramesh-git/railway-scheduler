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


def test_manual_add_and_cancel_replan(tmp_path, monkeypatch):
    """A raised cargo appears (pinned); a cancelled one is dropped and re-planned."""
    import trackservice.marine.requests_store as st
    monkeypatch.setattr(st, "_ADD", tmp_path / "add.jsonl")
    monkeypatch.setattr(st, "_CANCEL", tmp_path / "cancel.jsonl")
    from trackservice.marine import pipeline as pl

    base = pl.run(seed=3, weeks=12)
    n = base["metrics"]["total_parcels"]

    st.record_addition({"commodity": "Coking coal", "origin": "AUS", "port": "GGV",
                        "volume_t": 68000, "required_by_week": 9, "priority": 5})
    added = pl.run(seed=3, weeks=12)
    assert added["metrics"]["total_parcels"] == n + 1
    assert added["manual_ids"] == ["CR-001"]

    st.record_cancellation("CGO-005", "gm-commercial", "buyer pulled tender")
    after = pl.run(seed=3, weeks=12)
    assert "CGO-005" in after["cancelled"]
    assert not any(p["id"] == "CGO-005" for p in after["scenario"]["parcels"])


def test_audit_hierarchy_present():
    from trackservice.marine import pipeline as pl
    r = pl.run(seed=3, weeks=12)
    au = r["audit"]
    assert au["entries"] and "roles" in au
    ranks = {e["rank"] for e in au["entries"]}
    assert ranks  # seeded chain populated


def test_market_calibrated_to_baltic():
    from trackservice.marine import pipeline as pl
    r = pl.run(seed=3, weeks=12)
    assert r["market"]["BDI"] == 3178 and r["market"]["date"] == "2026-09-29"


def test_feeds_roundtrip(tmp_path):
    from trackservice.marine import feeds as fd
    from trackservice.marine.optimizer import optimize, verify
    fd.generate_sample_feeds(seed=3, weeks=12, feeds_dir=str(tmp_path))
    sc = fd.build_scenario_from_feeds(str(tmp_path))
    assert len(sc.parcels) == 24 and sc.weeks == 12
    plan = optimize(sc, time_limit=10.0)
    assert verify(sc, plan).ok
