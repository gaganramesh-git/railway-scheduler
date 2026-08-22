"""Why didn't this request get scheduled? Answer it empirically, not by guessing.

CP-SAT does not hand you a reason a variable landed at 0 in an *optimisation*
problem — it optimises, it doesn't justify. The original prototype papered over
this with a post-hoc heuristic ("crew looks saturated") and had to soften the
claim on stage to "diagnostic, not proof".

We do it properly. For an unscheduled request we relax one resource dimension at
a time, re-solve, and watch. If lifting crew capacity lets the request in and
lifting nothing else does, then crew capacity *is* the binding constraint — shown,
not asserted. It is the same move DataGate and WARDEN make: don't trust an
opinion about the cause, remove the suspect and replay.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from . import solver as _solver
from .types import CrewType, Equipment, ResourcePool, Scenario


@dataclass
class Explanation:
    request_id: str
    binding: list[str]        # dimensions that, when relaxed, let the request in
    detail: str               # human sentence for the conflict panel
    infeasible_alone: bool    # true = no window ever fits it, regardless of resources


# How much to loosen each dimension when testing it. Generous, because we only
# care whether the request *can* enter once that pressure is removed.
_BUMP = 4


def explain_unscheduled(scenario: Scenario, unscheduled: list[str]) -> list[Explanation]:
    return [_explain_one(scenario, rid) for rid in unscheduled]


def _explain_one(scenario: Scenario, request_id: str) -> Explanation:
    r = scenario.request(request_id)

    # First: is there any night whose window can physically hold it? If not, no
    # amount of crew or equipment will help — it's a structural miss.
    fits_somewhere = any(
        (w := scenario.window(r.section_id, n)) is not None and r.duration <= w.length
        for n in r.nights()
    )
    if not fits_somewhere:
        return Explanation(
            request_id=request_id,
            binding=["window"],
            detail=(
                f"No engineering block on {r.section_id} within nights "
                f"{r.earliest_night + 1}–{r.latest_night + 1} is long enough "
                f"for this {_hrs(r.duration)} job."
            ),
            infeasible_alone=True,
        )

    binding: list[str] = []
    if _enters_when(scenario, request_id, crew=r.crew):
        binding.append("crew")
    if r.equipment is not Equipment.NONE and _enters_when(
        scenario, request_id, equipment=r.equipment
    ):
        binding.append("equipment")

    return Explanation(
        request_id=request_id,
        binding=binding or ["contention"],
        detail=_phrase(scenario, r, binding),
        infeasible_alone=False,
    )


def _enters_when(
    scenario: Scenario,
    request_id: str,
    *,
    crew: CrewType | None = None,
    equipment: Equipment | None = None,
) -> bool:
    """Relax exactly one dimension, re-solve, and report whether the request got in."""
    relaxed = _relax(scenario, crew=crew, equipment=equipment)
    result = _solver.solve(relaxed, time_limit=3.0)
    return request_id in result.scheduled_ids


def _relax(
    scenario: Scenario,
    *,
    crew: CrewType | None,
    equipment: Equipment | None,
) -> Scenario:
    """A copy of the scenario with one resource dimension loosened.

    Crew relaxation also lifts the duty-hour ceiling, since the two together are
    what 'more crew available' really means on the ground.
    """
    pool = scenario.pool
    if crew is not None:
        new_crew = dict(pool.crew)
        new_crew[crew] = new_crew.get(crew, 0) + _BUMP
        pool = ResourcePool(new_crew, dict(pool.equipment), pool.crew_shift * (_BUMP + 1))
    if equipment is not None:
        new_eq = dict(pool.equipment)
        new_eq[equipment] = new_eq.get(equipment, 0) + _BUMP
        pool = ResourcePool(pool.crew, new_eq, pool.crew_shift)
    return replace(scenario, pool=pool)


def _phrase(scenario: Scenario, r, binding: list[str]) -> str:
    names = {
        "crew": f"{r.crew.value} crews were fully booked",
        "equipment": f"the {r.equipment.value} was already committed",
        "section": f"{r.section_id}'s block was taken by higher-priority work",
    }
    if not binding:
        return "Displaced by higher-weight work competing for the same night."
    parts = [names[b] for b in binding if b in names]
    lead = "Relaxing this let the job in: " if len(parts) == 1 else "Any of these would let it in: "
    return lead + "; ".join(parts) + "."


def _hrs(ticks: int) -> str:
    h = ticks / 2
    return f"{int(h)}h" if h == int(h) else f"{h:g}h"
