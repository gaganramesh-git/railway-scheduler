# Track Service

Maintenance block scheduling for railway engineering windows. **Statement 27**
(SIH 2026): *conflicting work requests, limited engineering windows, manual
coordination — software that detects conflicts, proposes alternatives, and
optimises the plan.*

It does the three things the statement asks for, and does the third one — the one
most teams skip — properly:

1. **Detect conflicts** — an OR-Tools CP-SAT model over sections, crews, machines
   and duty hours.
2. **Optimise** — maximise the priority weight actually scheduled, with a real
   first-come-first-served greedy baseline to measure against.
3. **Explain and propose** — for every job that didn't fit, *prove* why by
   relaxing one resource and re-solving, then propose a concrete alternative
   (what to bump, and what it costs).

## Quick start

```bash
uv venv --python 3.12 && uv pip install -e ".[dev,service]"
uv run trackservice run
```

That writes `schedule.json` and `dashboard.html`. **Open `dashboard.html`
directly — no server needed.** It embeds the data, uses no localStorage, and
runs offline.

```bash
uv run trackservice metrics      # just the numbers to quote
uv run trackservice sweep        # CP-SAT vs greedy across 5 seeds — proof it generalises
uv run trackservice serve        # live dashboard: a judge authors an emergency, solver places it live
```

`serve` starts a local (offline) server at http://127.0.0.1:8000. It serves the
dashboard in **live mode** — a "Custom emergency" form lets anyone invent an
emergency (section, night, duration, crew, equipment) and watch the real solver
re-plan and report what it bumped. The static `dashboard.html` remains the
can't-flake fallback; the server is the "try your own" upgrade.

## The pitch, in one paragraph

The story is not the headline count (CP-SAT schedules about as many jobs as
greedy). The story is *what each one drops*. Greedy places jobs in submission
order and loses high-priority work to bad luck of ordering; CP-SAT never does —
every job it drops is lowest-tier. `trackservice sweep` shows the priority-weight
gap holds across seeds, so it isn't one lucky dataset.

## Why the unscheduled reasons are trustworthy

CP-SAT does not explain why a variable landed at zero in an optimisation problem.
So instead of guessing ("crew looks saturated"), Track Service **relaxes exactly
one resource — crew, or equipment — re-solves, and checks whether the job now
fits.** If lifting crew capacity lets it in and lifting equipment doesn't, crew
was the binding constraint. Shown, not asserted — the same relax-and-replay move
behind the alternatives and the emergency re-plan.

## How it fits together

```
data.py       synthetic-but-plausible scenario (real maintenance templates)
   → solver.py     CP-SAT: no-overlap per section, cumulative crew + equipment, duty hours
   → greedy.py     honest FCFS baseline to beat
   → explain.py    relax-one-resource-and-re-solve  → why each job didn't fit
   → alternatives.py  force a job in, re-solve      → what it would cost to grant
   → export.py     one JSON contract
   → dashboard.py  self-contained HTML Gantt (before/after, conflicts, emergency)
```

Everything runs through `pipeline.run()`, so the demo and the tests exercise the
same code path.

## Units

Every time quantity is an integer count of **half-hour ticks** — windows,
durations, starts, duty budgets, all of them. Hours appear only at the data
boundary (`hours_to_ticks`) and in human-facing formatters. This is deliberate:
mixing raw hours into a tick-based model silently doubles resource capacity and
the schedule looks fine while ignoring its own limits. See the note at the top of
`types.py`.

## Scripts

| Command | What it does |
|---|---|
| `trackservice run` | Solve, explain, propose, inject emergency, write JSON + dashboard |
| `trackservice metrics` | Print the stage numbers only |
| `trackservice sweep` | CP-SAT-vs-greedy gap across seeds |
| `pytest` | Test suite |
