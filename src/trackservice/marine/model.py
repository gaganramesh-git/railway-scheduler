"""Domain model for bulk-cargo vessel chartering (SIH26006).

The planning problem: bulk cargo (mostly coal) must be procured from overseas
origins and delivered to India's East-Coast ports. For each cargo parcel we must
choose a vessel class and a departure week — cheaply, on time, and within the
physical limits of the discharge port (draft / LOA). Chartering earlier when the
freight market is soft, and consolidating parcels into fewer larger voyages, is
where the money is saved.

This mirrors the block-planner's shape: scarce, constrained slots (here: vessel
voyages under port limits) packed against demands with deadlines (here: cargo
required-by weeks), optimised instead of booked reactively at spot.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Port:
    """A discharge port on India's East Coast. `max_draft_m` is the binding
    physical constraint — a vessel drawing more water simply cannot berth."""
    id: str
    name: str
    max_draft_m: float
    max_loa_m: float
    handling_rate_tpd: int   # tonnes/day discharge — sets turnaround/idle


@dataclass(frozen=True)
class Origin:
    """An overseas loading region and its sailing time to the East Coast."""
    id: str
    name: str
    transit_weeks: int


@dataclass(frozen=True)
class VesselClass:
    """A dry-bulk vessel class. Bigger classes carry cheaper $/tonne but need
    deeper ports, so port draft caps which classes can serve which parcel."""
    id: str
    name: str
    dwt: int          # deadweight tonnes (capacity)
    draft_m: float
    loa_m: float
    # $/tonne base hire — larger vessels are cheaper per tonne (economies of scale)
    base_rate_per_t: float


@dataclass(frozen=True)
class CargoParcel:
    """One demand: a volume of a commodity from an origin to a port, needed by a
    week. `required_by_week` is the hard deadline — a stockout if missed."""
    id: str
    commodity: str
    origin_id: str
    port_id: str
    volume_t: int
    required_by_week: int
    priority: int          # 3 routine .. 5 critical (plant-critical coal)


@dataclass(frozen=True)
class Voyage:
    """A candidate chartered voyage the optimiser may or may not use: a vessel
    class sailing one origin→port lane, departing a given week."""
    id: str
    vessel_id: str
    origin_id: str
    port_id: str
    depart_week: int
    capacity_t: int
    cost: float            # total hire for this voyage (rate depends on week)


@dataclass
class Assignment:
    parcel_id: str
    voyage_id: str
    vessel_id: str
    origin_id: str
    port_id: str
    depart_week: int
    arrive_week: int
    volume_t: int


@dataclass
class CharterPlan:
    status: str = "UNKNOWN"
    solve_seconds: float = 0.0
    proven_optimal: bool = False
    assignments: list[Assignment] = field(default_factory=list)
    unserved: list[str] = field(default_factory=list)
    total_cost: float = 0.0
    voyages_used: int = 0

    @property
    def served_ids(self) -> set[str]:
        return {a.parcel_id for a in self.assignments}


@dataclass(frozen=True)
class Scenario:
    ports: list[Port]
    origins: list[Origin]
    vessels: list[VesselClass]
    parcels: list[CargoParcel]
    weeks: int
    # freight-rate index per (vessel_id, week) — a multiplier on base_rate_per_t
    rate_index: dict = field(default_factory=dict)
    seed: int = 0

    def port(self, pid: str) -> Port:
        return next(p for p in self.ports if p.id == pid)

    def origin(self, oid: str) -> Origin:
        return next(o for o in self.origins if o.id == oid)

    def vessel(self, vid: str) -> VesselClass:
        return next(v for v in self.vessels if v.id == vid)

    def parcel(self, pid: str) -> CargoParcel:
        return next(p for p in self.parcels if p.id == pid)

    def rate(self, vessel_id: str, week: int) -> float:
        return self.rate_index.get((vessel_id, week), 1.0)
