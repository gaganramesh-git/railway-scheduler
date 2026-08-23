"""End-to-end run: build data, solve both ways, explain, propose, inject emergency.

This is the one function the CLI and the tests both call, so the demo and the
test suite exercise identical code.
"""

from __future__ import annotations

from . import alternatives as alt
from . import data as _data
from . import export as _export
from . import greedy as _greedy
from . import solver as _solver
from .explain import explain_unscheduled


def run(
    seed: int = 7,
    n_requests: int = 40,
    nights: int = 5,
    explain: bool = True,
    custom_emergency=None,
    input_csv: str | None = None,
) -> dict:
    if input_csv:
        from . import importer as _importer

        scenario = _importer.load_scenario(input_csv, nights=nights, seed=seed)
    else:
        scenario = _data.build_scenario(seed=seed, n_requests=n_requests, nights=nights)

    optimal = _solver.solve(scenario, time_limit=10.0)
    greedy = _greedy.schedule_greedy(scenario)

    explanations = explain_unscheduled(scenario, optimal.unscheduled) if explain else []

    # Propose alternatives for the highest-priority things we had to drop.
    to_offer = sorted(
        optimal.unscheduled,
        key=lambda rid: scenario.request(rid).priority.value,
        reverse=True,
    )[:5]
    alternatives = [alt.propose_for(scenario, optimal, rid) for rid in to_offer]

    emergency = _run_emergency(scenario, optimal, custom_emergency)

    return _export.build_report(
        scenario, optimal, greedy, explanations, alternatives, emergency
    )


def _run_emergency(scenario, baseline, custom=None) -> dict:
    """Inject an emergency after planning closed, force it in, report the cost.

    `custom` is an optional pre-built Request (from a live judge form). When None,
    we synthesise the default rail-fracture on the busiest section.
    """
    emg = custom if custom is not None else _data.emergency_request(scenario, night=0)
    injected = scenario.with_request(emg)
    reoptimised = alt.force_schedule(injected, emg.id, baseline)

    bumped = sorted(baseline.scheduled_ids - reoptimised.scheduled_ids)

    # force_schedule inflates the emergency's weight so the solver must place it,
    # which pollutes schedule.objective. Report the TRUE priority weight instead —
    # the honest sum of real priorities over what's actually scheduled.
    true_weight = sum(
        injected.request(a.request_id).priority.value
        for a in reoptimised.assignments
    )
    payload = _export.schedule_payload(reoptimised)
    payload["objective"] = true_weight
    metrics = _export.metrics(injected, reoptimised)
    metrics["priority_weight"] = true_weight

    return {
        "kind": "emergency",
        "request": {
            "id": emg.id,
            "title": emg.title,
            "section": emg.section_id,
            "night": emg.earliest_night,
        },
        "scenario": _export.scenario_payload(injected),
        "schedule": payload,
        "metrics": metrics,
        "bumped": bumped,
        "weight_before": baseline.objective,
        "weight_after": true_weight,
    }


def run_apply(seed=7, n_requests=40, nights=5, apply_ids=None) -> dict:
    """Commit one or more proposed alternatives: force the pinned jobs into the plan,
    re-solve, and return a fresh report showing the applied change.

    `apply_ids` is the *cumulative* set of pins (each Apply click sends the whole
    running list), so the optimiser rebuilds one plan that honours all of them at
    once. Same engine as the emergency path; the change rides in the report's
    `emergency` slot (tagged kind='applied') so the dashboard renders it the same way.
    """
    apply_ids = apply_ids or []
    scenario = _data.build_scenario(seed=seed, n_requests=n_requests, nights=nights)
    optimal = _solver.solve(scenario, time_limit=10.0)
    greedy = _greedy.schedule_greedy(scenario)

    applied = _run_apply(scenario, optimal, apply_ids)

    # Alternatives for whatever is *still* dropped after these pins.
    pinned_scheduled = set(applied["pinned_scheduled"])
    remaining = sorted(
        (rid for rid in optimal.unscheduled if rid not in pinned_scheduled),
        key=lambda rid: scenario.request(rid).priority.value,
        reverse=True,
    )[:5]
    alternatives = [alt.propose_for(scenario, optimal, rid) for rid in remaining]
    explanations = explain_unscheduled(scenario, optimal.unscheduled)

    return _export.build_report(
        scenario, optimal, greedy, explanations, alternatives, applied
    )


def _run_apply(scenario, baseline, apply_ids) -> dict:
    """Force the pinned requests into the plan and report what it displaced."""
    reoptimised = alt.force_schedule_many(scenario, apply_ids, baseline)
    scheduled_now = reoptimised.scheduled_ids

    pinned_scheduled = [rid for rid in apply_ids if rid in scheduled_now]
    pinned_failed = [rid for rid in apply_ids if rid not in scheduled_now]
    # Anything present now that wasn't in the original optimal plan was displaced-in
    # or shuffled; the honest "bumped" list is what the baseline had and we lost.
    bumped = sorted(baseline.scheduled_ids - scheduled_now)

    true_weight = sum(
        scenario.request(a.request_id).priority.value for a in reoptimised.assignments
    )
    payload = _export.schedule_payload(reoptimised)
    payload["objective"] = true_weight
    metrics = _export.metrics(scenario, reoptimised)
    metrics["priority_weight"] = true_weight

    # The banner describes the most-recently-clicked pin (last in the list).
    last = apply_ids[-1] if apply_ids else None
    r = scenario.request(last) if last else None
    a = reoptimised.assignment(last) if last else None
    return {
        "kind": "applied",
        "request": {
            "id": r.id if r else "",
            "title": r.title if r else "",
            "section": r.section_id if r else "",
            "night": (a.night if a else (r.earliest_night if r else 0)),
        },
        "pinned": list(apply_ids),
        "pinned_scheduled": pinned_scheduled,
        "pinned_failed": pinned_failed,
        "scenario": _export.scenario_payload(scenario),
        "schedule": payload,
        "metrics": metrics,
        "bumped": bumped,
        "weight_before": baseline.objective,
        "weight_after": true_weight,
    }
