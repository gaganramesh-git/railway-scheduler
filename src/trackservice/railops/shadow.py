"""Shadow / integrated block detection — the coordination win BDMS can't make.

BDMS has the buttons for shadow and integrated blocks, but it waits for a human
to *notice* the opportunity. Its own report — "Integrated Blocks — No Associated
Block Demanded" — exists to count how often that noticing fails.

We find them automatically. When two departments' jobs are scheduled on the same
section on the same night, they sit inside one corridor closure — so they need
one block demand between them, not two. Formalising that as a shadow/integrated
block frees a whole corridor. Corridor time is the scarce resource, so "fewer
blocks demanded for the same work done" is the metric that matters.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class ShadowProposal:
    section_id: str
    section_name: str
    night: int
    job_ids: list[str]
    departments: list[str]
    corridors_saved: int
    note: str


def detect(scenario, schedule, meta) -> tuple[list[ShadowProposal], int]:
    """Scan pending demands for cross-department pairs that could share one block.

    A shadow opportunity exists when two demands from different departments sit on
    the same section, their feasible-night ranges overlap, and there is a common
    night whose engineering window can hold them together (they work in parallel
    inside one closure). Formalising the pair as one integrated block frees a
    corridor. Returns (ranked proposals, total corridors saved).
    """
    section_name = {s.id: s.name for s in scenario.sections}
    traffic = {s.id: s.traffic_density for s in scenario.sections}

    # Longest window available on each section, and the nights it exists.
    win_len: dict[str, int] = defaultdict(int)
    nights_with_window: dict[str, set[int]] = defaultdict(set)
    for w in scenario.windows:
        win_len[w.section_id] = max(win_len[w.section_id], w.length)
        nights_with_window[w.section_id].add(w.night)

    by_section: dict[str, list] = defaultdict(list)
    for r in scenario.requests:
        by_section[r.section_id].append(r)

    proposals: list[ShadowProposal] = []
    total_saved = 0
    seen: set[str] = set()  # a demand joins at most one shadow

    for sec, reqs in by_section.items():
        reqs = sorted(reqs, key=lambda r: r.id)
        for i in range(len(reqs)):
            a = reqs[i]
            if a.id in seen or a.id not in meta:
                continue
            for j in range(i + 1, len(reqs)):
                b = reqs[j]
                if b.id in seen or b.id not in meta:
                    continue
                if meta[a.id].department == meta[b.id].department:
                    continue
                lo = max(a.earliest_night, b.earliest_night)
                hi = min(a.latest_night, b.latest_night)
                shared_nights = [n for n in range(lo, hi + 1) if n in nights_with_window[sec]]
                if not shared_nights:
                    continue
                # Parallel work inside one closure: block must hold the longer job.
                if max(a.duration, b.duration) > win_len[sec]:
                    continue
                night = shared_nights[0]
                depts = sorted({meta[a.id].department, meta[b.id].department})
                proposals.append(
                    ShadowProposal(
                        section_id=sec,
                        section_name=section_name.get(sec, sec),
                        night=night,
                        job_ids=[a.id, b.id],
                        departments=depts,
                        corridors_saved=1,
                        note=(
                            f"{depts[0]} {a.id} and {depts[1]} {b.id} both want {sec} "
                            f"({section_name.get(sec, sec)}) around night {night + 1} — "
                            f"raise one integrated block instead of two, save a corridor."
                        ),
                    )
                )
                total_saved += 1
                seen.add(a.id)
                seen.add(b.id)
                break  # a is now paired

    # Busiest sections first — the corridor saved there is worth most.
    proposals.sort(key=lambda p: traffic.get(p.section_id, 0), reverse=True)
    return proposals, total_saved
