# Track Service — Demo Script

**Statement 92 · Railway maintenance scheduling · SIH 2026**

> Backwards-planned from one moment: **a live emergency re-plan that bumps the
> right jobs, proves why, and loses zero priority.** Everything else exists to set
> that up. Nothing is typed live. The dataset is fixed (seed 7); the emergency is
> pre-seeded; a screen recording is queued as backup.

Total run time: **~4 minutes.** Two people is enough.

---

## Roles

- **Driver** — clicks only. Never speaks. Knows the exact click order below.
- **Narrator** — speaks only. Never touches the machine. Watches the clock.
- (Optional **Backup** — finger on the recorded video, ready if the laptop dies.)

## Pre-flight checklist (do this before you're called up)

- [ ] `uv run trackservice run` has been run today; `dashboard.html` opens clean.
- [ ] `dashboard.html` open in the browser, **full screen**, zoomed so blocks are readable from the back of the room.
- [ ] Sitting on **Night 1**, **Optimised (CP-SAT)** view, emergency **off**.
- [ ] A second terminal ready with `trackservice sweep` already typed, **not** yet run.
- [ ] **If you plan to offer "judge drives it":** a third terminal with `trackservice serve` **already running**, and `http://127.0.0.1:8000` open in a second browser tab, sitting on the base view. Test one live solve before you go up. If the server isn't up and ready, don't offer it — fall back to the scripted emergency.
- [ ] Screen recording of a full successful run saved locally and findable in 5 seconds.
- [ ] Brightness up, notifications off, wifi off (the whole thing runs offline — prove it if asked).

## The numbers you will quote (seed 7 — memorise these)

| | CP-SAT | Greedy FCFS |
|---|---|---|
| Scheduled | **34/40** | 30/40 |
| Priority weight | **120** | 107 |
| Window utilisation | 43.5% | 39.0% |
| Solve time | **0.024s, OPTIMAL (proven)** | — |

- Weight gap this run: **+13**. Across 5 seeds: **+16 mean, CP-SAT never loses.**
- Emergency: rail fracture on SEC-H, re-solved in **0.03s**, bumps 3 routine jobs, weight **120 → 120 (zero net loss).**

---

## The performance, beat by beat

### COLD OPEN — how it's planned today · 0:00–0:30

*(Screen already showing the **Before (greedy FCFS)** view, Night 1. Open on the problem, not on your names.)*

> **Narrator:** "Every night, Indian Railways hands a few track sections over for
> maintenance — a handful of hours, no trains. Signalling, track, overhead-line and
> bridge teams all want those windows. Today a divisional engineer reconciles it by
> hand, on spreadsheets and phone calls. First come, first served."

*(Driver: slowly click through **Night 1 → 2 → 3**, letting the gaps and the thin schedule sit.)*

> "This is that manual method, run honestly on 40 real work requests. It's legal —
> nothing overlaps, no crew is double-booked. But look what it leaves on the table."

### THE TURN — same night, same data · 0:30–1:15

*(Driver: click **Optimised (CP-SAT)**. Stay on the same night so the change is visible in place.)*

> **Narrator:** "Same 40 requests. Same windows. Same crews. This is our optimiser."

*(Driver: let the KPI row settle. Point nothing — let them read it.)*

> "Thirty jobs scheduled becomes thirty-four. But the count isn't the story — **the
> story is *which* jobs.** Greedy drops work by accident of who filed first. It shed
> three *important* jobs this run purely from ordering. Our engine drops only the
> lowest-priority work, and it proves it's optimal — a hundred and twenty priority
> points versus a hundred and seven. Solved in **twenty-four milliseconds.**"

### THE PROOF — why didn't these fit? · 1:15–2:10

*(Driver: scroll to the **Conflict report** panel.)*

> **Narrator:** "Now — the honest part, and the part every other team skips. When a
> job doesn't fit, we don't shrug, and we don't guess."

*(Driver: rest on the **WR-024** row — "Relaxing this let the job in: OHE crews were fully booked.")*

> "The solver can't tell you *why* a job didn't make the cut. So we find out
> experimentally: we give it one more OHE crew, re-solve, and the job walks in.
> Take the crew away, it doesn't. That's not an opinion — that's the binding
> constraint, **demonstrated.**"

*(Driver: rest on **WR-005** — the `window` tag, "no block is long enough".)*

> "And here's one we're not too proud to show: WR-005, an urgent rail-fracture job,
> **can't be scheduled by anyone** — its section has no engineering window long
> enough. Greedy silently drops it too; the difference is *we say so, and we say
> why.* A planner who's told the truth can go get a longer window."

### THE HERO — the 2 a.m. emergency · 2:10–3:05

*(Narrator sets it up before the click.)*

> **Narrator:** "Planning's closed. It's 2 a.m. A rail fracture is reported on the
> busiest suburban section. It has to be worked tonight. Watch."

*(Driver: click **⚠ Inject emergency**.)*

> *(The banner fires. Let it land.)*

> "Re-planned in **thirty milliseconds.** The fracture is in — and the tool tells the
> planner exactly what it moved to make room: three routine jobs bumped, each
> re-placed on another night. And the total priority of the plan? **Unchanged.** It
> didn't sacrifice important work to absorb the emergency — it reshuffled the
> routine. *That* is 'propose alternatives' — the third thing the problem statement
> asks for, and the one nobody else will show you."

### THE CLOSER — not one lucky dataset · 3:05–3:45

*(Driver: switch to the second terminal, run `trackservice sweep`.)*

> **Narrator:** "One good demo could be a fluke. So we ran it across five different
> datasets."

*(Driver: let the table finish.)*

> "Every single one, the optimiser beats greedy on priority — by sixteen points on
> average, and it **never once loses.** Same code, exact solutions, proven optimal,
> all under a tenth of a second."

> **Narrator (final):** "The statement asked for three things — detect conflicts,
> optimise the plan, propose alternatives. **We do all three, we do the third one
> live, and we prove every claim instead of asserting it.** That's Track Service."

*(Stop. Don't add a slide. Don't say 'any questions'. Let it end on the line.)*

---

## OPTIONAL — "judge drives it" · only if they push

This is not part of the 4-minute run. It's a response, held in reserve for one
trigger: **a judge asks, in some form, "is this pre-recorded?" or "can it handle
a case you didn't prepare?"** That question is the opening — don't force this
segment if it never comes.

The whole scripted demo runs off the static `dashboard.html`, which can't fail.
This segment is the *only* moment you switch to the live server. You are trading
your safety net for something a canned demo physically cannot do: solve an input
nobody at the table has seen.

**How to hand over:**

> **Narrator:** "Fair question. Everything so far ran off a fixed file, on purpose —
> so it can't flake on stage. But the solver is real. Give me a scenario. Any
> section, any night, any kind of failure."

*(Driver: switch to the browser tab already on `http://127.0.0.1:8000`. Open the
**✦ Custom emergency** form. Then turn the laptop toward the judge, or fill the
fields as they call them out.)*

> "You pick it. Section, night, how long the job takes, which crew."

*(Judge chooses. Driver clicks **Solve it →**.)*

> *(The plan re-draws in well under a second.)*

> "That's the real optimiser, on a scenario none of us prepared. It placed your
> emergency, it's telling you exactly what it moved to fit it, and it re-checked
> the whole night to stay legal. Same engine, live."

**Reading the result out loud — three cases, all wins:**

- **It bumped some jobs, weight held** → "It absorbed your emergency and gave up
  nothing that matters — it reshuffled routine work, not priority work."
- **It bumped nothing** → "There was slack there — it slotted straight in, no
  disruption at all."
- **Your emergency couldn't be fully honoured** *(rare; only on a genuinely
  impossible ask)* → "And notice it's not pretending — it's telling you this can't
  be done as stated, which is exactly what a planner needs to hear before 2 a.m.,
  not after."

**Recovery — if it goes sideways:**

- **Judge picks something dull** (fits with no bumps, looks anticlimactic) → own
  it: "That one had room — let me show you a tight one," and re-solve on SEC-H
  (the busiest section) night 1, which forces visible bumps.
- **Server hiccups or the tab's not responding** → don't fight it. "The live
  server's being shy — but you saw it run; here's the same thing on the built-in
  case," and click the scripted **⚠ Inject emergency** on the static tab. You lose
  nothing that matters.
- **Judge fat-fingers the form** → it won't crash; bad values snap to safe ones and
  it still solves. Just read whatever it returns.

**The one rule:** offer this *only* if the server was up and tested before you went
on. A failed live moment is worse than never offering it. When in doubt, stay on
the static demo and answer the "pre-recorded?" question with the sweep instead.

---

## Q&A — the questions that will come, and how to answer

**"Is this real railway data?"**
> Honest answer: the *scenario* is synthetic, built from real maintenance activity
> types — tamping, ballast cleaning, OHE work, rail-fracture repair — with realistic
> durations and crew needs. The *engine* is real and data-agnostic: feed it an
> actual division's requests and windows and nothing changes. We generated data so
> we could show you the hard cases on demand; we didn't need to fake the solver.

**"Why not just use the greedy scheduler? It scheduled almost as many."**
> Because count isn't the objective — priority is. Greedy's misses are high-value
> jobs it drops by luck of ordering. Ours are provably the lowest-value jobs
> possible. On safety-critical work, "we happened to schedule a similar number" is
> not good enough.

**"You call it 'proof' — is it really?"**
> For the *conflict reasons*, yes, and it's empirical, not a claim: we relax one
> resource, re-solve, and observe whether the job now fits. For *optimality*, CP-SAT
> returns a proven-optimal certificate on this instance — the status is OPTIMAL, not
> just 'feasible'. We're careful to only say 'proven' where we can back it.

**"Will this scale to a whole zone, not 40 requests?"**
> The model is the standard OR-Tools cumulative-scheduling formulation, which scales
> to thousands of tasks; the honest limit is that very large instances may return a
> strong feasible solution under a time cap rather than a proven-optimal one. For a
> division-night — which is the real planning unit — it's milliseconds.

**"What's actually live versus pre-recorded?"**
> The solver is genuinely running — the sweep you just watched solved five datasets
> live. The main dashboard's states are pre-computed so the demo can't flake on
> stage; that's a reliability choice, not a limitation. We can run any seed live if
> you want to pick one.

**"How is the emergency different from just re-running it?"**
> It's a *forced* re-solve: the emergency is pinned as must-schedule, and the
> optimiser finds the minimum-cost way to honour it. The bumped list and the
> zero-loss result are the optimiser's answer, not ours.

---

## If something breaks

- Dashboard won't load → open the saved screen recording, narrate over it. The
  script above works word-for-word against the video.
- Sweep errors in the terminal → skip it, say "we've run it across five seeds, mean
  gap sixteen points, it never loses" and go straight to the closer.
- Asked to run a live seed and it's slow → it won't be (all seeds solve < 0.1s), but
  if pressed, `trackservice metrics --seed <n>` prints the numbers with no browser.
