"""Propose alternatives — the third thing the problem statement literally asks for.

Detecting conflicts and optimising the plan are the easy two-thirds. The ask that
teams skip is: when a request can't be granted, *offer something*. We do it by
forcing the request into the plan and re-solving — the optimiser then tells us
exactly which lower-value work it would displace to make room, and what that
costs in scheduled priority weight. The planner sees a real trade, not a shrug.

This is also the mechanism behind the emergency scenario: an emergency is just a
must-schedule request, and the bumped list is its proposal.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import solver as _solver
from .types import Schedule, Scenario


@dataclass
class Alternative:
    request_id: str
    feasible: bool             # could it be forced in at all?
    bumped: list[str]          # requests displaced to make room
    weight_cost: int           # priority weight given up (positive = a net loss)
    night: int | None          # where it would land
    note: str


def propose_for(
    scenario: Scenario,
    baseline: Schedule,
    request_id: str,
) -> Alternative:
    """What would it take to grant `request_id`, given the current baseline plan?"""
    forced = _force(scenario, request_id)
    trial = _solver.solve(forced, time_limit=5.0)

    if request_id not in trial.scheduled_ids:
        return Alternative(
            request_id=request_id,
            feasible=False,
            bumped=[],
            weight_cost=0,
            night=None,
            note="Cannot be granted even by displacing other work — no feasible slot exists.",
        )

    bumped = sorted(baseline.scheduled_ids - trial.scheduled_ids)
    a = trial.assignment(request_id)
    cost = baseline.objective - trial.objective  # weight sacrificed vs. the optimal plan
    return Alternative(
        request_id=request_id,
        feasible=True,
        bumped=bumped,
        weight_cost=cost,
        night=a.night if a else None,
        note=_note(scenario, request_id, bumped, cost, a.night if a else None),
    )


def force_schedule(scenario: Scenario, request_id: str, baseline: Schedule) -> Schedule:
    """Re-solve with `request_id` pinned in — the 'accept this alternative' action.

    Used for the emergency injection: pin the emergency, warm-start from the
    baseline so the re-solve is fast, and return the new plan.
    """
    return force_schedule_many(scenario, [request_id], baseline)


def force_schedule_many(scenario: Scenario, ids, baseline: Schedule) -> Schedule:
    """Re-solve with several jobs pinned in at once — cumulative 'Apply' clicks.

    Each pinned job is worth more than every normal job combined, so the optimiser
    schedules as many of them as are *jointly* feasible before it packs the rest.
    If two pins genuinely can't coexist, one won't appear — the caller compares
    against `ids` to see which pins were honoured.
    """
    forced = _force(scenario, set(ids))
    return _solver.solve(forced, time_limit=5.0, warm_start=baseline)


def _force(scenario: Scenario, request_ids) -> Scenario:
    """Scenario in which every id in `request_ids` is (near-)mandatory.

    Rather than thread a must-schedule flag through the model, we lift each pinned
    request's weight far above the sum of all normal work, so any optimal plan
    schedules them if they are jointly feasible. Clean and solver-agnostic.
    """
    from dataclasses import replace

    ids = {request_ids} if isinstance(request_ids, str) else set(request_ids)
    total = sum(r.priority.value for r in scenario.requests)
    big = total + 1  # one pinned job outweighs all normal work combined
    boosted = [
        replace(r, priority=_HugePriority(big)) if r.id in ids else r
        for r in scenario.requests
    ]
    return replace(scenario, requests=boosted)


class _HugePriority(int):
    """An int that also answers `.value`, so it drops into the weight expression
    wherever a Priority enum would. Keeps the solver oblivious to the boost."""

    @property
    def value(self) -> int:  # type: ignore[override]
        return int(self)


def _note(scenario, request_id, bumped, cost, night) -> str:
    r = scenario.request(request_id)
    where = f"night {night + 1}" if night is not None else "an available night"
    if not bumped:
        return f"Fits on {where} with no displacement — grant it directly."
    titles = ", ".join(
        f"{b} ({scenario.request(b).title})" for b in bumped[:3]
    )
    more = f" and {len(bumped) - 3} more" if len(bumped) > 3 else ""
    trade = "no net weight lost" if cost <= 0 else f"costs {cost} priority weight"
    return f"Grant on {where} by bumping {titles}{more} — {trade}."
