"""Independent constraint checker — a second opinion on every plan.

This module shares NO code with the solver, on purpose. The solver is clever and
could have a bug; a clever verifier might inherit the same bug. So this one is
deliberately dumb: it re-derives every hard constraint from the raw plan with
plain loops, and fails the plan if any is violated. Standard practice in
safety-critical scheduling — cheap to build, and it means a flawed plan is never
handed to a controller marked "final".

It answers one question: is this plan physically and legally valid?
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Verification:
    ok: bool = True
    violations: list[str] = field(default_factory=list)
    checks_run: int = 0

    def fail(self, msg: str) -> None:
        self.ok = False
        self.violations.append(msg)


def verify(scenario, schedule, mandatory: set[str] | None = None) -> Verification:
    """Re-check the plan against every hard rule, from scratch."""
    v = Verification()
    mandatory = set(mandatory or ())
    req = {r.id: r for r in scenario.requests}
    win = {(w.section_id, w.night): w for w in scenario.windows}
    placed = {a.request_id: a for a in schedule.assignments}

    # 1. Each job placed at most once, on an allowed night, inside its window.
    for a in schedule.assignments:
        r = req.get(a.request_id)
        v.checks_run += 1
        if r is None:
            v.fail(f"{a.request_id}: placed but not a known demand")
            continue
        if not (r.earliest_night <= a.night <= r.latest_night):
            v.fail(f"{a.request_id}: night {a.night+1} outside allowed {r.earliest_night+1}-{r.latest_night+1}")
        w = win.get((r.section_id, a.night))
        if w is None:
            v.fail(f"{a.request_id}: no engineering window on {r.section_id} night {a.night+1}")
        elif a.start < w.start or a.end > w.end:
            v.fail(f"{a.request_id}: {a.start}-{a.end} spills the window {w.start}-{w.end}")
        if a.end - a.start != r.duration:
            v.fail(f"{a.request_id}: duration {a.end-a.start} ≠ demanded {r.duration}")

    # 2. No two blocks overlap on the same section on the same night.
    by_slot = defaultdict(list)
    for a in schedule.assignments:
        r = req.get(a.request_id)
        if r:
            by_slot[(r.section_id, a.night)].append(a)
    for (sec, night), items in by_slot.items():
        items.sort(key=lambda a: a.start)
        for x, y in zip(items, items[1:]):
            v.checks_run += 1
            if x.end > y.start:
                v.fail(f"{sec} night {night+1}: {x.request_id} and {y.request_id} overlap")

    # 3. Crew and 4. equipment capacity, per night (independent tally).
    crew_cap = scenario.pool.crew  # dict CrewType -> int
    equip_cap = scenario.pool.equipment
    for night in range(scenario.nights):
        # sweep-line peak concurrency per resource
        _peak_check(v, by_slot, req, night, key=lambda r: r.crew,
                    size=lambda r: r.crew_size, cap=crew_cap, label="crew")
        _peak_check(v, by_slot, req, night, key=lambda r: r.equipment,
                    size=lambda r: 1, cap=equip_cap, label="equipment",
                    skip=lambda val: getattr(val, "value", val) == "none")

    # 5. Crew duty hours: total booked crew-ticks per type per night ≤ budget.
    shift = scenario.pool.crew_shift
    for night in range(scenario.nights):
        load = defaultdict(int)
        for (sec, n), items in by_slot.items():
            if n != night:
                continue
            for a in items:
                r = req[a.request_id]
                load[r.crew] += r.duration * r.crew_size
        for crew, booked in load.items():
            v.checks_run += 1
            budget = crew_cap.get(crew, 0) * shift
            if booked > budget:
                v.fail(f"{getattr(crew,'value',crew)} night {night+1}: duty {booked} > budget {budget}")

    # 6. Statutory jobs: every mandatory job that is feasible must be placed on time.
    for rid in mandatory:
        v.checks_run += 1
        if rid not in placed:
            # Only a violation if it was physically schedulable somewhere.
            r = req[rid]
            feasible = any(
                (w := win.get((r.section_id, n))) and r.duration <= (w.end - w.start)
                for n in range(r.earliest_night, r.latest_night + 1)
            )
            if feasible:
                v.fail(f"STATUTORY {rid}: schedulable but not placed within deadline")

    return v


def _peak_check(v, by_slot, req, night, key, size, cap, label, skip=None):
    """Sweep-line peak concurrency for one resource dimension on one night."""
    events = defaultdict(list)  # resource-value -> [(tick, delta)]
    for (sec, n), items in by_slot.items():
        if n != night:
            continue
        for a in items:
            r = req[a.request_id]
            val = key(r)
            if skip and skip(val):
                continue
            events[val].append((a.start, size(r)))
            events[val].append((a.end, -size(r)))
    for val, evs in events.items():
        evs.sort(key=lambda e: (e[0], e[1]))  # releases before acquires at same tick
        cur = peak = 0
        for _, d in evs:
            cur += d
            peak = max(peak, cur)
        v.checks_run += 1
        limit = cap.get(val, 0)
        if peak > limit:
            v.fail(f"{label} {getattr(val,'value',val)} night {night+1}: peak {peak} > capacity {limit}")
