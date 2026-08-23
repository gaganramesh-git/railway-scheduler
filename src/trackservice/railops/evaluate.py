"""Phase 7 — the evidence. Run many scenarios, measure our plan against the
manual/first-come-first-served baseline, and report the result with its spread.

We measure what the model can measure honestly. CRIS's own BDMS Reports module
names four coordination failures; two of them (Approved-but-Not-Granted,
Extended / Spilled-Over Blocks) need real BDMS grant-and-duration history to
count, so we do not fake them — they are future work once a BDMS export exists.
The failures we *can* measure directly, we do:

  Statutory deadline violations   safety — a T0 job past its manual clock
  Overdue (unscheduled) work      asset arrears
  Asset unavailability            traffic-weighted block-hours (the objective)
  Missed shadow opportunities     maps to "Integrated Blocks — No Associated
                                  Block": corridors a manual planner leaves
                                  un-shared because nobody noticed
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev

from .. import greedy as _greedy
from .. import solver as _solver
from . import generator as _gen
from . import shadow as _shadow


@dataclass
class Row:
    statutory_met: float
    statutory_total: float
    statutory_violations: float
    scheduled: float
    overdue: float
    asset_unavail: float   # traffic-weighted block-hours (lower = better)
    shadows_found: float   # coordination wins a manual planner misses


# A live speed restriction from an unaddressed defect costs far more availability
# than the block that clears it. An unfixed IMR/UML means ~a day of trains crawling.
_PSR_HOURS = 10.0  # traffic-weighted availability lost per night an urgent defect stays open


def _measure(scenario, meta, schedule, t0, shadows_found) -> Row:
    traffic = {s.id: s.traffic_density for s in scenario.sections}
    avg_t = mean(traffic.values())
    placed = schedule.scheduled_ids

    met = len(t0 & placed)

    # Asset unavailability = short-term block cost + ongoing speed-restriction cost.
    # Clearing a defect costs a block tonight; NOT clearing it leaves the line
    # restricted every night until it's done — which is the larger cost. This is
    # the objective inversion: doing urgent maintenance *raises* availability.
    unavail = 0.0
    for a in schedule.assignments:
        r = scenario.request(a.request_id)
        hours = (a.end - a.start) / 2
        unavail += hours * (traffic[r.section_id] / avg_t)  # the block itself
    for r in scenario.requests:
        m = meta.get(r.id)
        if r.id not in placed and m and m.tier <= 1:  # overdue urgent/statutory defect
            unavail += _PSR_HOURS * (traffic[r.section_id] / avg_t)  # ongoing PSR

    return Row(
        statutory_met=met,
        statutory_total=len(t0),
        statutory_violations=len(t0) - met,
        scheduled=len(placed),
        overdue=len(scenario.requests) - len(placed),
        asset_unavail=round(unavail, 1),
        shadows_found=shadows_found,
    )


def run_eval(seeds: int = 20, nights: int = 7) -> dict:
    ours: list[Row] = []
    base: list[Row] = []

    for s in range(seeds):
        scenario, meta = _gen.build_scenario(seed=s, nights=nights)
        t0 = {rid for rid, m in meta.items() if m.tier == 0}

        opt = _solver.solve(scenario, time_limit=10.0, mandatory=t0)
        grd = _greedy.schedule_greedy(scenario)

        # Our system proposes shadows; the manual baseline proposes none.
        _, saved = _shadow.detect(scenario, opt, meta)

        ours.append(_measure(scenario, meta, opt, t0, shadows_found=saved))
        base.append(_measure(scenario, meta, grd, t0, shadows_found=0))

    def agg(rows, attr):
        vals = [getattr(r, attr) for r in rows]
        return mean(vals), pstdev(vals)

    metrics = [
        ("Statutory deadlines met", "statutory_met", "higher"),
        ("Statutory VIOLATIONS", "statutory_violations", "lower"),
        ("Jobs scheduled", "scheduled", "higher"),
        ("Overdue (unscheduled)", "overdue", "lower"),
        ("Asset unavailability (wt block-h)", "asset_unavail", "lower"),
        ("Shadow corridors found", "shadows_found", "higher"),
    ]
    result = {"seeds": seeds, "t0_per_scenario": ours[0].statutory_total, "metrics": []}
    for label, attr, better in metrics:
        om, osd = agg(ours, attr)
        bm, bsd = agg(base, attr)
        result["metrics"].append({
            "label": label, "better": better,
            "ours_mean": round(om, 2), "ours_sd": round(osd, 2),
            "base_mean": round(bm, 2), "base_sd": round(bsd, 2),
        })
    return result


if __name__ == "__main__":
    from rich.console import Console
    from rich.table import Table

    r = run_eval()
    t = Table(title=f"Phase 7 — evidence across {r['seeds']} scenarios "
                     f"(real corridor, {int(r['t0_per_scenario'])} statutory jobs each)")
    for c in ("Metric", "Ours (CP-SAT)", "Manual / FIFO", "Better"):
        t.add_column(c)
    for m in r["metrics"]:
        ours = f"{m['ours_mean']} ± {m['ours_sd']}"
        base = f"{m['base_mean']} ± {m['base_sd']}"
        win = "✓ ours" if (
            (m["better"] == "higher" and m["ours_mean"] > m["base_mean"]) or
            (m["better"] == "lower" and m["ours_mean"] < m["base_mean"])
        ) else ("= tie" if m["ours_mean"] == m["base_mean"] else "✗")
        t.add_row(m["label"], ours, base, win)
    Console().print(t)
