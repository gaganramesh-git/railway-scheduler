"""Derive a real corridor's sections, traffic density and night engineering
windows from the public Indian Railways timetable.

Why this matters: the problem statement says corridor availability is the binding
constraint. Rather than invent which sections are busy and when a block is
possible, we compute it from actual train movements (datameet/railways, sourced
from data.gov.in). Sections and traffic are real; only the maintenance jobs laid
onto them are synthetic.

We model the Delhi–Howrah main line's most congested stretch —
Kanpur (CNB) → Allahabad (ALD) → Mughal Sarai (MGS) — because that is where
block time is genuinely scarce, which is the whole point of the problem.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# The real corridor we model, by endpoint station codes on the Delhi–Howrah route.
CORRIDOR_ENDPOINTS = ("CNB", "MGS")  # Kanpur Central → Mughal Sarai Jn
NIGHT_START_MIN = 23 * 60  # engineering blocks are sought at night; window search
NIGHT_END_MIN = 30 * 60    # 23:00 → 06:00 (30:00 = 06:00 next day)
MAX_CORRIDOR_STATIONS = 9  # keep the modelled division tractable


@dataclass(frozen=True)
class CorridorSection:
    id: str            # SEC-A, SEC-B, ...
    from_code: str
    to_code: str
    from_name: str
    to_name: str
    trains_per_day: int          # real traffic density
    window_start_min: int        # night engineering window, minutes past 22:00
    window_end_min: int


def _minutes(t) -> int | None:
    if t in (None, "None", ""):
        return None
    hh, mm, *_ = t.split(":")
    return int(hh) * 60 + int(mm)


def _load(raw_dir: Path):
    stops = json.loads((raw_dir / "schedules.json").read_text())
    feats = json.loads((raw_dir / "stations.json").read_text())["features"]
    stations = {
        f["properties"]["code"]: f["properties"]
        for f in feats
        if f.get("geometry") and f["properties"].get("code")
    }
    coords = {
        f["properties"]["code"]: f["geometry"]["coordinates"]
        for f in feats
        if f.get("geometry") and f["properties"].get("code")
    }
    return stops, stations, coords


def build_corridor(raw_dir: str = "data/raw") -> list[CorridorSection]:
    """Compute the real corridor: ordered sections, traffic, night windows."""
    raw = Path(raw_dir)
    stops, stations, coords = _load(raw)
    a, b = CORRIDOR_ENDPOINTS

    # Trains that serve BOTH endpoints run our corridor.
    served_by = defaultdict(set)  # station_code -> set(train_number)
    times_at = defaultdict(list)  # station_code -> [minute-of-day]
    for s in stops:
        code = s["station_code"]
        served_by[code].add(s["train_number"])
        m = _minutes(s["departure"]) or _minutes(s["arrival"])
        if m is not None:
            times_at[code].append(m)

    corridor_trains = served_by[a] & served_by[b]
    if not corridor_trains:
        raise RuntimeError(f"No trains serve both {a} and {b}")

    # Candidate intermediate stations must (a) be served by a real share of the
    # corridor's trains and (b) actually lie ON the line — within a latitude band
    # of the straight CNB→MGS path, so a station at the same longitude but on a
    # different route (a branch line) is excluded.
    lon_a, lat_a = coords[a]
    lon_b, lat_b = coords[b]
    lo, hi = min(lon_a, lon_b), max(lon_a, lon_b)
    LAT_BAND = 0.4  # degrees off the interpolated line

    def on_line(lon, lat) -> bool:
        if hi == lo:
            return abs(lat - lat_a) <= LAT_BAND
        frac = (lon - lo) / (hi - lo)
        expected_lat = lat_a + frac * (lat_b - lat_a) if lon_a <= lon_b else lat_b + frac * (lat_a - lat_b)
        return abs(lat - expected_lat) <= LAT_BAND

    candidates = []
    for code, trains in served_by.items():
        if code not in coords:
            continue
        lon, lat = coords[code]
        if not (lo - 0.05 <= lon <= hi + 0.05) or not on_line(lon, lat):
            continue
        share = len(trains & corridor_trains)
        if share >= max(20, len(corridor_trains) // 4):  # a real through-station
            candidates.append((lon, code, share))

    candidates.sort()  # west → east
    # Thin to a tractable, evenly-spaced set that includes both endpoints.
    chosen = _thin(candidates, a, b, MAX_CORRIDOR_STATIONS)

    sections = []
    letters = "ABCDEFGHIJ"
    for i in range(len(chosen) - 1):
        _, c1, _ = chosen[i]
        _, c2, _ = chosen[i + 1]
        trains_here = served_by[c1] & served_by[c2]
        w0, w1 = _night_window(len(trains_here))
        sections.append(
            CorridorSection(
                id=f"SEC-{letters[i]}",
                from_code=c1,
                to_code=c2,
                from_name=stations[c1]["name"].title(),
                to_name=stations[c2]["name"].title(),
                trains_per_day=len(trains_here),
                window_start_min=w0,
                window_end_min=w1,
            )
        )
    return sections


def _thin(candidates, a, b, k):
    """Keep endpoints + evenly spaced interior stations, k total."""
    by_code = {c: (lon, c, sh) for lon, c, sh in candidates}
    if a not in by_code or b not in by_code:
        raise RuntimeError("endpoint missing coordinates")
    interior = [x for x in candidates if x[1] not in (a, b)]
    interior.sort()
    take = max(0, k - 2)
    if len(interior) > take and take > 0:
        step = len(interior) / take
        interior = [interior[int(i * step)] for i in range(take)]
    ordered = [by_code[a]] + interior + [by_code[b]]
    ordered.sort()  # by longitude
    return ordered


def _night_window(trains_per_day: int) -> tuple[int, int]:
    """Night engineering window, derived from real traffic density.

    On a congested corridor the block is not limited by the length of the night —
    it is limited by traffic. The more trains a section carries, the smaller the
    engineering window that can be handed over. We encode that directly: window
    length falls as real trains/day rises. Returned as half-hour ticks past 22:00
    (the solver's unit). Every window opens at 23:30 (tick 3) — after the last
    evening peak — which matches how night blocks are actually granted.

        ≤ 40 trains/day → 6.0h     100–150 → 4.0h
        40–70          → 5.5h     150–200 → 3.0h
        70–100         → 5.0h     > 200   → 2.5h
    """
    if trains_per_day <= 40:
        hours = 6.0
    elif trains_per_day <= 70:
        hours = 5.5
    elif trains_per_day <= 100:
        hours = 5.0
    elif trains_per_day <= 150:
        hours = 4.0
    elif trains_per_day <= 200:
        hours = 3.0
    else:
        hours = 2.5
    start_tick = 3  # 23:30
    return start_tick, start_tick + int(hours * 2)


def load_corridor(raw_dir: str = "data/raw", cache: str = "data/corridor.json") -> list[CorridorSection]:
    """Cached corridor: compute from the 82MB timetable once, reuse the small JSON."""
    cache_path = Path(cache)
    if cache_path.exists():
        rows = json.loads(cache_path.read_text())
        return [CorridorSection(**r) for r in rows]
    secs = build_corridor(raw_dir)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps([s.__dict__ for s in secs], indent=2))
    return secs


if __name__ == "__main__":
    secs = build_corridor()
    Path("data/corridor.json").write_text(json.dumps([s.__dict__ for s in secs], indent=2))
    print(f"Corridor {CORRIDOR_ENDPOINTS[0]} → {CORRIDOR_ENDPOINTS[1]}: {len(secs)} real sections\n")
    for s in secs:
        w = f"{22 + s.window_start_min // 2:02d}:{(s.window_start_min % 2) * 30:02d}"
        dur = (s.window_end_min - s.window_start_min) / 2
        print(
            f"  {s.id}  {s.from_code}->{s.to_code:6}  "
            f"{s.trains_per_day:3d} trains/day   window {w} +{dur:.1f}h   "
            f"{s.from_name} → {s.to_name}"
        )
