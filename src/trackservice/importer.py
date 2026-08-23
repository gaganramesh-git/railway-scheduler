"""Load real maintenance work requests from a CSV — so the engine runs on *your*
data, not just the synthetic scenario.

The CSV carries the transactional work requests; the sections, engineering
windows and resource pool come from the base scenario (in a real deployment these
are master data fed from the railway's systems). This keeps the import a thin,
honest boundary: swap the requests, keep the environment.

Expected columns (header row required; extra columns ignored):
    id, title, section, duration_h, priority, crew, crew_size, equipment,
    earliest_night, latest_night

- priority:   URGENT/IMPORTANT/ROUTINE  (or 5/4/3)
- crew:       p-way | signalling | ohe | bridge
- equipment:  tamping-machine | ballast-cleaner | rail-grinder | tower-wagon |
              road-railer | none
- nights are 1-based in the file, converted to 0-based internally
Bad rows are reported, not silently dropped.
"""

from __future__ import annotations

import csv
from dataclasses import replace

from . import data as _data
from .types import CrewType, Equipment, Priority, Request, Scenario, hours_to_ticks

_PRIORITY = {
    "urgent": Priority.URGENT, "5": Priority.URGENT,
    "important": Priority.IMPORTANT, "4": Priority.IMPORTANT,
    "routine": Priority.ROUTINE, "3": Priority.ROUTINE,
}


class ImportError_(ValueError):
    """A CSV that can't be read as work requests, with a row-level reason."""


def load_scenario(path: str, nights: int = 5, seed: int = 7) -> Scenario:
    """Read work requests from `path` onto the base scenario's sections/windows/pool."""
    base = _data.build_scenario(seed=seed, nights=nights)
    section_ids = {s.id for s in base.sections}
    requests = _read_requests(path, section_ids, nights)
    if not requests:
        raise ImportError_("No valid work requests found in the file.")
    return replace(base, requests=requests)


def _read_requests(path: str, section_ids: set[str], nights: int) -> list[Request]:
    out: list[Request] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ImportError_("File is empty or has no header row.")
        cols = {c.strip().lower() for c in reader.fieldnames}
        required = {"id", "title", "section", "duration_h", "priority", "crew"}
        missing = required - cols
        if missing:
            raise ImportError_(f"Missing required columns: {', '.join(sorted(missing))}.")

        for n, row in enumerate(reader, start=2):  # row 1 is the header
            r = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
            if not r.get("id"):
                continue  # skip blank lines
            try:
                out.append(_row_to_request(r, section_ids, nights))
            except Exception as e:  # noqa: BLE001 — surface the row, keep going
                raise ImportError_(f"Row {n} ({r.get('id', '?')}): {e}") from e
    return out


def _row_to_request(r: dict, section_ids: set[str], nights: int) -> Request:
    section = r["section"].upper()
    if section not in section_ids:
        raise ValueError(f"unknown section '{section}' (known: {', '.join(sorted(section_ids))})")

    prio = _PRIORITY.get(r["priority"].lower())
    if prio is None:
        raise ValueError(f"bad priority '{r['priority']}' (use URGENT/IMPORTANT/ROUTINE)")

    try:
        crew = CrewType(r["crew"].lower())
    except ValueError:
        raise ValueError(f"bad crew '{r['crew']}' (use {', '.join(c.value for c in CrewType)})")

    equip_raw = (r.get("equipment") or "none").lower()
    try:
        equip = Equipment(equip_raw)
    except ValueError:
        raise ValueError(f"bad equipment '{equip_raw}'")

    dur_h = float(r["duration_h"])
    if dur_h <= 0:
        raise ValueError("duration_h must be positive")

    earliest = int(r.get("earliest_night") or 1) - 1  # file is 1-based
    latest = int(r.get("latest_night") or nights) - 1
    earliest = max(0, min(earliest, nights - 1))
    latest = max(earliest, min(latest, nights - 1))

    return Request(
        id=r["id"].upper(),
        title=r["title"],
        section_id=section,
        duration=hours_to_ticks(round(dur_h * 2) / 2),  # snap to half-hour
        priority=prio,
        crew=crew,
        crew_size=int(r.get("crew_size") or 1),
        equipment=equip,
        earliest_night=earliest,
        latest_night=latest,
    )
