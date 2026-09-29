"""File adapters for the chartering inputs — the marine counterpart of the railway
module's integrations layer. Reads the four masters plus the freight-rate feed from
CSV, and can write realistic samples from a scenario:

  port_master.csv    — discharge ports and their draft/LOA limits
  vessels.csv        — dry-bulk vessel classes
  origins.csv        — overseas loading regions and transit weeks
  cargo_demand.csv   — the procurement demand list (what to ship, by when)
  freight_rates.csv  — the market: a $/tonne index per vessel class per week
                       (drop in licensed Baltic BCI/BPI/BSI/BHSI history here)
"""

from __future__ import annotations

import csv
from pathlib import Path

from . import data as _data
from .model import CargoParcel, Origin, Port, Scenario, VesselClass

FEEDS_DIR = "data/marine_feeds"


def load_port_master(path: str) -> list[Port]:
    with open(path, newline="") as f:
        return [Port(r["id"], r["name"], float(r["max_draft_m"]), float(r["max_loa_m"]),
                     int(r["handling_tpd"])) for r in csv.DictReader(f)]


def load_vessels(path: str) -> list[VesselClass]:
    with open(path, newline="") as f:
        return [VesselClass(r["id"], r["name"], int(r["dwt"]), float(r["draft_m"]),
                            float(r["loa_m"]), float(r["base_rate_per_t"]))
                for r in csv.DictReader(f)]


def load_origins(path: str) -> list[Origin]:
    with open(path, newline="") as f:
        return [Origin(r["id"], r["name"], int(r["transit_weeks"])) for r in csv.DictReader(f)]


def load_cargo_demand(path: str) -> list[CargoParcel]:
    with open(path, newline="") as f:
        return [CargoParcel(r["id"], r["commodity"], r["origin"], r["port"],
                            int(r["volume_t"]), int(r["required_by_week"]), int(r["priority"]))
                for r in csv.DictReader(f)]


def load_freight_rates(path: str) -> tuple[dict, int]:
    idx, weeks = {}, 0
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            w = int(r["week"])
            idx[(r["vessel_id"], w)] = float(r["index"])
            weeks = max(weeks, w + 1)
    return idx, weeks


def build_scenario_from_feeds(feeds_dir: str = FEEDS_DIR) -> Scenario:
    d = Path(feeds_dir)
    ports = load_port_master(str(d / "port_master.csv"))
    vessels = load_vessels(str(d / "vessels.csv"))
    origins = load_origins(str(d / "origins.csv"))
    parcels = load_cargo_demand(str(d / "cargo_demand.csv"))
    rate_index, weeks = load_freight_rates(str(d / "freight_rates.csv"))
    return Scenario(ports=ports, origins=origins, vessels=vessels, parcels=parcels,
                    weeks=weeks, rate_index=rate_index, seed=0)


def export_feeds(scenario: Scenario, feeds_dir: str = FEEDS_DIR) -> None:
    d = Path(feeds_dir)
    d.mkdir(parents=True, exist_ok=True)

    with open(d / "port_master.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["id", "name", "max_draft_m", "max_loa_m", "handling_tpd"])
        for p in scenario.ports:
            w.writerow([p.id, p.name, p.max_draft_m, p.max_loa_m, p.handling_rate_tpd])

    with open(d / "vessels.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["id", "name", "dwt", "draft_m", "loa_m", "base_rate_per_t", "baltic_index"])
        for v in scenario.vessels:
            w.writerow([v.id, v.name, v.dwt, v.draft_m, v.loa_m, v.base_rate_per_t,
                        _data.VESSEL_INDEX.get(v.id, "")])

    with open(d / "origins.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["id", "name", "transit_weeks"])
        for o in scenario.origins:
            w.writerow([o.id, o.name, o.transit_weeks])

    with open(d / "cargo_demand.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "commodity", "origin", "port", "volume_t", "required_by_week", "priority"])
        for p in scenario.parcels:
            w.writerow([p.id, p.commodity, p.origin_id, p.port_id, p.volume_t,
                        p.required_by_week, p.priority])

    with open(d / "freight_rates.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["vessel_id", "baltic_index", "week", "index",
                    f"# calibrated to Baltic {_data.BALTIC['date']}"])
        for v in scenario.vessels:
            for wk in range(scenario.weeks):
                w.writerow([v.id, _data.VESSEL_INDEX.get(v.id, ""), wk,
                            scenario.rate(v.id, wk), ""])


def generate_sample_feeds(seed: int = 3, weeks: int = 12, feeds_dir: str = FEEDS_DIR) -> dict:
    scenario = _data.build_scenario(seed=seed, weeks=weeks)
    export_feeds(scenario, feeds_dir)
    return {"feeds_dir": feeds_dir, "parcels": len(scenario.parcels),
            "ports": len(scenario.ports), "vessels": len(scenario.vessels),
            "rate_rows": len(scenario.vessels) * weeks, "baltic": _data.BALTIC}
