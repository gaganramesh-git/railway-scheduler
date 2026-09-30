"""Realistic (but synthetic) data for the chartering problem, plus the freight-rate
series and forecast. Figures are representative of India's East-Coast coal trade;
live deployments would read ports/vessels from masters and rates from a market feed.
"""

from __future__ import annotations

import random

from .model import CargoParcel, Origin, Port, Scenario, VesselClass, Voyage

# Real Baltic Exchange dry-bulk snapshot the market model is calibrated to. The
# sub-indices map one-to-one onto our vessel classes; a licensed Baltic history
# feed drops straight into freight_rates.csv (see marine/feeds.py).
BALTIC = {
    "date": "2026-09-29",
    "source": "Baltic Exchange (via Trading Economics)",
    "BDI": 3178, "BCI": 5103, "BPI": 2390, "BSI": 1797, "BHSI": 745,
}
# vessel class -> Baltic sub-index, and that class's recent weekly volatility
VESSEL_INDEX = {"CAPE": "BCI", "PANA": "BPI", "SUPRA": "BSI", "HANDY": "BHSI"}
_WEEKLY_VOL = {"CAPE": 0.075, "PANA": 0.045, "SUPRA": 0.038, "HANDY": 0.030}

# East-Coast India discharge ports — max draft is the binding limit.
PORTS = [
    Port("PPT", "Paradip",        18.0, 300, 60000),
    Port("VZG", "Visakhapatnam",  17.0, 290, 55000),
    Port("GGV", "Gangavaram",     21.0, 320, 70000),   # deepest — takes Capesize
    Port("GPL", "Gopalpur",       14.5, 240, 35000),
    Port("DHM", "Dhamra",         18.5, 300, 60000),
    Port("HDA", "Haldia",         10.5, 230, 30000),   # shallow — Handysize only (draft-capped)
]

# Overseas loading regions and transit time to the East Coast.
ORIGINS = [
    Origin("AUS", "Australia (Hay Point)",   3),
    Origin("IDN", "Indonesia (Kalimantan)",  2),
    Origin("USA", "USA (Baltimore)",         6),
    Origin("MOZ", "Mozambique (Maputo)",     4),
    Origin("RUS", "Russia (Vostochny)",      4),
]

# Dry-bulk classes: bigger = cheaper $/tonne, but deeper draft.
VESSELS = [
    VesselClass("HANDY", "Handysize", 35000, 10.0, 180, 22.0),
    VesselClass("SUPRA", "Supramax",  58000, 12.5, 200, 18.5),
    VesselClass("PANA",  "Panamax",   75000, 14.0, 229, 16.0),
    VesselClass("CAPE",  "Capesize", 180000, 18.0, 290, 12.5),
]

_COMMODITIES = ["Coking coal", "Thermal coal", "Steam coal"]

INR_PER_USD = 88  # freight is USD-quoted (Baltic); we display in INR at this rate


def inr(usd: float) -> str:
    """Format a USD amount as INR (crore / lakh) for display."""
    r = usd * INR_PER_USD
    if r >= 1e7:
        return f"₹{r/1e7:,.2f} cr"
    if r >= 1e5:
        return f"₹{r/1e5:,.2f} L"
    return f"₹{r:,.0f}"


# East-Coast ports ordered north -> south along the coastline, so "next nearest"
# is the closest neighbour that can still physically take the cargo.
PORT_ORDER = ["HDA", "DHM", "PPT", "GPL", "VZG", "GGV"]


def nearest_feasible_port(scenario, port_id: str, volume_t: int) -> "Port | None":
    """The closest coastal port (to `port_id`) that can berth a vessel large enough
    for `volume_t`. Used when a port goes unavailable and cargo must be rerouted."""
    order = {pid: i for i, pid in enumerate(PORT_ORDER)}
    here = order.get(port_id, 0)
    cap_ok = lambda p: any(v.dwt >= volume_t and v.draft_m <= p.max_draft_m
                           and v.loa_m <= p.max_loa_m for v in scenario.vessels)
    others = [p for p in scenario.ports if p.id != port_id and cap_ok(p)]
    others.sort(key=lambda p: abs(order.get(p.id, 99) - here))
    return others[0] if others else None


def _rate_series(vessels, weeks, rng) -> dict:
    """A freight-rate index per (vessel, week): a market that starts at today's
    Baltic level (week 0 = 1.0) and evolves as a mean-reverting random walk whose
    weekly volatility is calibrated to each class's real Baltic sub-index. This is
    what timing optimisation exploits — charter in a soft week, not at the deadline.
    Replace with real Baltic history via freight_rates.csv for a live deployment."""
    idx = {}
    for v in vessels:
        vol = _WEEKLY_VOL.get(v.id, 0.04)
        level = 1.0
        for w in range(weeks):
            idx[(v.id, w)] = round(level, 3)
            shock = rng.gauss(0, vol)
            revert = 0.15 * (1.0 - level)          # pull back toward the mean
            level = max(0.7, min(1.4, level + shock + revert))
    return idx


def build_scenario(seed: int = 3, weeks: int = 12, n_parcels: int | None = None) -> Scenario:
    rng = random.Random(seed)
    if n_parcels is None:
        n_parcels = max(12, weeks * 2)

    rate_index = _rate_series(VESSELS, weeks, rng)

    # Largest parcel a port can physically take = biggest vessel that can berth it.
    max_vol_at = {
        p.id: max((v.dwt for v in VESSELS
                   if v.draft_m <= p.max_draft_m and v.loa_m <= p.max_loa_m), default=0)
        for p in PORTS
    }

    parcels: list[CargoParcel] = []
    for i in range(1, n_parcels + 1):
        origin = rng.choice(ORIGINS)
        port = rng.choice(PORTS)
        # volumes cluster around vessel sizes so consolidation matters, but never
        # exceed what the chosen port can physically receive.
        cap = max_vol_at[port.id]
        volume = rng.choice([v for v in [28000, 30000, 45000, 55000, 68000, 70000] if v <= cap]
                            or [min(28000, cap)])
        # deadline leaves room to sail (transit) plus slack the optimiser can use
        earliest_arrive = origin.transit_weeks
        req_by = min(weeks - 1, earliest_arrive + rng.randint(2, max(2, weeks - earliest_arrive - 1)))
        tier = rng.choice([5, 5, 4, 4, 3])
        parcels.append(CargoParcel(
            id=f"CGO-{i:03d}",
            commodity=rng.choice(_COMMODITIES),
            origin_id=origin.id,
            port_id=port.id,
            volume_t=volume,
            required_by_week=req_by,
            priority=tier,
        ))

    return Scenario(ports=PORTS, origins=ORIGINS, vessels=VESSELS, parcels=parcels,
                    weeks=weeks, rate_index=rate_index, seed=seed)


def candidate_voyages(scenario: Scenario) -> list[Voyage]:
    """Every legal voyage the optimiser may choose: a vessel class on an origin→port
    lane departing a week, but only where the vessel physically fits the port."""
    out: list[Voyage] = []
    n = 0
    for o in scenario.origins:
        for p in scenario.ports:
            for v in scenario.vessels:
                if v.draft_m > p.max_draft_m or v.loa_m > p.max_loa_m:
                    continue  # vessel cannot berth here — infeasible lane
                for w in range(scenario.weeks):
                    if w + o.transit_weeks > scenario.weeks - 1:
                        continue  # would arrive after the horizon
                    n += 1
                    cost = round(v.base_rate_per_t * v.dwt * scenario.rate(v.id, w), 0)
                    out.append(Voyage(
                        id=f"V{n:04d}", vessel_id=v.id, origin_id=o.id, port_id=p.id,
                        depart_week=w, capacity_t=v.dwt, cost=cost,
                    ))
    return out


def forecast_entry(scenario: Scenario, vessel_id: str, latest_week: int) -> dict:
    """Recommend the cheapest departure week up to a deadline for a vessel class —
    the 'optimal market-entry timing' output."""
    weeks = [w for w in range(latest_week + 1)]
    rates = [(w, scenario.rate(vessel_id, w)) for w in weeks]
    best_w, best_r = min(rates, key=lambda x: x[1])
    now_r = scenario.rate(vessel_id, 0)
    return {
        "vessel": vessel_id,
        "best_week": best_w,
        "best_index": best_r,
        "spot_now_index": now_r,
        "saving_pct": round(100 * (now_r - best_r) / now_r, 1) if now_r else 0.0,
    }
