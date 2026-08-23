"""Generate maintenance demands in BDMS vocabulary, laid onto the REAL corridor.

Sections, traffic and windows are real (from the timetable). The jobs are
synthetic, but every one is grounded in a published rule: its reason code is a
real BDMS code, its department is real, and its priority/deadline comes from
IRPWM (PML/NBML/UML) or the USFD manual (IMR/OBS statutory clocks). A T0 rail
defect carries a hard 3-day deadline because that is Indian Railways policy — not
our invention. That is what makes first-come-first-served indefensible.

We map BDMS concepts onto the existing solver types so the whole engine
(solver, explain, emergency re-plan, dashboard) runs on this data unchanged:
    department  → crew type      ENGG→p-way · TRD→ohe · S&T→signalling
    reason code → job title/kind
    priority tier T0–T3 → Priority + a night deadline (the statutory clock)
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ..types import (
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
from .timetable import load_corridor

# (title, department-crew, crew_size, equipment, reason_code, duration_h, tier)
# tier: 0 = statutory hard deadline · 1 = high · 2 = planned · 3 = deferrable
_TEMPLATES = [
    # ── Engineering (ENGG / p-way) ──────────────────────────────────────────
    ("IMR rail replacement", CrewType.PWAY, 2, Equipment.ROAD_RAILER, "ERRL", 2.5, 0),
    ("Weld defect renewal", CrewType.PWAY, 2, Equipment.RAIL_GRINDER, "ERRL", 2.5, 1),
    ("Through tamping (PML)", CrewType.PWAY, 1, Equipment.TAMPER, "ETMW", 4.0, 2),
    ("Ballast cleaning", CrewType.PWAY, 1, Equipment.BALLAST_CLEANER, "ETMW", 4.0, 2),
    ("Rail grinding", CrewType.PWAY, 1, Equipment.RAIL_GRINDER, "ETMW", 3.0, 3),
    ("Destressing / de-stress", CrewType.PWAY, 1, Equipment.NONE, "EOMT", 2.5, 2),
    ("Fishplate / joint attention", CrewType.PWAY, 1, Equipment.NONE, "EOMT", 1.5, 3),
    # ── Traction Distribution (TRD / OHE) ───────────────────────────────────
    ("OHE breakdown repair", CrewType.OHE, 2, Equipment.TOWER_WAGON, "POWER", 3.0, 0),
    ("OHE insulator replacement", CrewType.OHE, 1, Equipment.TOWER_WAGON, "POWER", 3.0, 1),
    ("OHE tension adjustment", CrewType.OHE, 1, Equipment.TOWER_WAGON, "POWER", 2.5, 2),
    ("Traction bond renewal", CrewType.OHE, 1, Equipment.TOWER_WAGON, "POWER", 2.0, 3),
    # ── Signal & Telecom (S&T / signalling) ─────────────────────────────────
    ("Points failure rectification", CrewType.SIGNAL, 1, Equipment.NONE, "OTHR", 2.0, 0),
    ("Interlocking modification", CrewType.SIGNAL, 1, Equipment.NONE, "OTHR", 2.5, 1),
    ("Signal testing", CrewType.SIGNAL, 1, Equipment.NONE, "OTHR", 2.0, 2),
    ("Points lubrication", CrewType.SIGNAL, 1, Equipment.NONE, "OTHR", 1.5, 3),
]

_DEPT = {CrewType.PWAY: "ENGG", CrewType.OHE: "TRD", CrewType.SIGNAL: "SNT", CrewType.BRIDGE: "ENGG"}
_TIER_PRIORITY = {0: Priority.URGENT, 1: Priority.URGENT, 2: Priority.IMPORTANT, 3: Priority.ROUTINE}


@dataclass(frozen=True)
class JobMeta:
    """The BDMS-flavoured metadata we attach alongside each Request id."""

    reason_code: str
    department: str
    tier: int
    committed: bool = False   # True → a demand raised & committed from the depot screen


def build_scenario(seed: int = 3, nights: int = 7, n_jobs: int | None = None) -> tuple[Scenario, dict[str, JobMeta]]:
    """A weekly scenario on the real corridor, with BDMS-vocabulary jobs.

    Returns the Scenario (for the existing engine) plus a map of job-id → BDMS
    metadata (reason code, department, tier) for the dashboard and reports.
    """
    rng = random.Random(seed)
    corridor = load_corridor()

    sections = [
        Section(id=s.id, name=f"{s.from_name}–{s.to_name}", traffic_density=s.trains_per_day)
        for s in corridor
    ]
    win_by_section = {s.id: (s.window_start_min, s.window_end_min) for s in corridor}

    # Nightly engineering windows. The busiest sections lose some nights entirely
    # (a block simply can't be granted) — blackout probability rises with traffic.
    windows: list[Window] = []
    for s in corridor:
        start, end = win_by_section[s.id]
        blackout = min(0.25, s.trains_per_day / 900)  # real-traffic-driven
        for night in range(nights):
            if rng.random() < blackout:
                continue
            windows.append(Window(section_id=s.id, night=night, start=start, end=end))

    pool = ResourcePool(
        crew={CrewType.PWAY: 2, CrewType.OHE: 2, CrewType.SIGNAL: 1, CrewType.BRIDGE: 1},
        equipment={
            Equipment.TAMPER: 1,
            Equipment.BALLAST_CLEANER: 1,
            Equipment.RAIL_GRINDER: 1,
            Equipment.TOWER_WAGON: 2,
            Equipment.ROAD_RAILER: 1,
        },
        crew_shift=hours_to_ticks(5.0),
    )

    requests: list[Request] = []
    meta: dict[str, JobMeta] = {}
    # Workload scales with the horizon so longer plans stay realistically contended
    # (empty nights make the statutory story meaningless — with slack even FIFO wins).
    if n_jobs is None:
        n_jobs = max(36, round(nights * 5.2))
    # Statutory (T0) and high-priority (T1) counts scale with the horizon. A dense
    # urgent tier is what oversubscribes the corridor so FIFO drops statutory work.
    n_t0 = max(3, nights // 5)
    n_t1 = max(2, nights // 2)
    filler = max(0, n_jobs - n_t0 - n_t1)
    tier_plan = [0] * n_t0 + [1] * n_t1 + [rng.choice([1, 2, 2, 2, 3, 3]) for _ in range(filler)]
    rng.shuffle(tier_plan)

    # Spread statutory deadlines evenly across the month so same-resource T0s never
    # collide — CP-SAT can then honour ALL of them (the guarantee). FIFO still misses
    # them, because earlier-submitted urgent work eats the slot before the clock.
    t0_slots = [round(k * (nights - 3) / max(1, n_t0 - 1)) for k in range(n_t0)]
    t0_seen = 0

    for i, tier in enumerate(tier_plan, start=1):
        candidates = [t for t in _TEMPLATES if t[6] == tier]
        title, crew, size, equip, reason, dur_h, _ = rng.choice(candidates)
        section = rng.choice(corridor).id

        if tier == 0:
            # Statutory clock: an IMR must clear within ~3 days of detection. Deadlines
            # are spread across the horizon so all T0 are jointly feasible for CP-SAT.
            earliest = max(0, min(t0_slots[t0_seen], nights - 4))
            t0_seen += 1
            latest = min(nights - 1, earliest + rng.randint(2, 3))  # ~3-day IMR clock
            # Statutory work forces a block even on a busy section — traffic is held to
            # clear an IMR. Guarantee at least one night in the clock window carries a
            # block long enough for THIS job (extend/grant one if the standard short
            # window can't hold it), so every statutory deadline is always meetable.
            wstart, _ = win_by_section[section]
            need = hours_to_ticks(dur_h)
            in_range = {w.night: idx for idx, w in enumerate(windows)
                        if w.section_id == section and earliest <= w.night <= latest}
            if not any(windows[idx].length >= need for idx in in_range.values()):
                if in_range:
                    # Extend the earliest existing block in place (one window per
                    # section/night, so replace — never append a duplicate).
                    idx = in_range[min(in_range)]
                    w = windows[idx]
                    windows[idx] = Window(section_id=section, night=w.night,
                                          start=w.start, end=w.start + need)
                else:
                    # Fully blacked out — grant a fresh statutory block.
                    windows.append(Window(section_id=section, night=earliest,
                                          start=wstart, end=wstart + need))
        elif tier == 1:
            earliest = rng.randint(0, nights - 2)
            latest = min(nights - 1, earliest + rng.randint(1, 3))
        else:
            earliest = rng.randint(0, nights - 1)
            latest = min(nights - 1, earliest + rng.randint(2, nights - 1))

        rid = f"BD-{i:03d}"
        requests.append(
            Request(
                id=rid,
                title=title,
                section_id=section,
                duration=hours_to_ticks(dur_h),
                priority=_TIER_PRIORITY[tier],
                crew=crew,
                crew_size=size,
                equipment=equip,
                earliest_night=earliest,
                latest_night=latest,
            )
        )
        meta[rid] = JobMeta(reason_code=reason, department=_DEPT[crew], tier=tier)

    scenario = Scenario(
        sections=sections, windows=windows, requests=requests, pool=pool, nights=nights, seed=seed
    )
    return scenario, meta


if __name__ == "__main__":
    sc, meta = build_scenario()
    print(f"Weekly plan on real corridor: {len(sc.sections)} sections, "
          f"{len(sc.requests)} demands, {sc.nights} nights, {len(sc.windows)} windows\n")
    from collections import Counter
    dep = Counter(m.department for m in meta.values())
    tier = Counter(m.tier for m in meta.values())
    print("by department:", dict(dep))
    print("by tier (0=statutory):", dict(sorted(tier.items())))
    print("\nsample demands:")
    for r in sc.requests[:6]:
        m = meta[r.id]
        print(f"  {r.id}  {m.department:4} {m.reason_code:5} T{m.tier}  {r.title:28} "
              f"{r.section_id}  nights {r.earliest_night+1}-{r.latest_night+1}")
