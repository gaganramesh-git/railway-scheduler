# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are the chartering and procurement team of an Indian bulk-material
importer (e.g. a steel producer sourcing coking/thermal coal), working a rolling
weekly-to-monthly planning horizon. The product serves an approval chain, each
seeing and doing only what their rank allows:

- **Chartering Officer** — raises cargo requirements at the desk (cannot cancel booked shipments).
- **Procurement Manager** — approves within budget; can cancel/reschedule/reroute in-department.
- **Logistics Head (DGM Materials)** — validates lanes and port limits; declares port disruptions.
- **GM (Commercial)** — signs off the plan; cancel/reschedule/reroute with a logged reason.
- **Director (Finance) / Board** — read-only aggregate oversight.

Their job: get every cargo to an East-Coast port on time, at the lowest freight cost,
within the physical limits of the ships and ports — instead of buying ships reactively
on the spot market one cargo at a time.

## Product Purpose

SIH26006 (Ministry of Steel) — "Intelligent Freight Forecasting & Optimised Vessel
Chartering." The product turns reactive, manual, daily spot chartering into a
proactive, coordinated, optimised plan. For each bulk-cargo parcel it decides the
vessel class and the departure week, so that delivery deadlines are met, freight cost
and vessel idle time are minimised, and cargo is consolidated onto fewer, fuller ships.
Success = a verified charter plan that is measurably cheaper and uses fewer charters
than reactive spot procurement, with every cargo delivered on time.

## Positioning

A constraint-optimisation engine (Google OR-Tools CP-SAT), not a forecasting
dashboard and not a reactive spot desk. What a neighbouring tool could not truthfully
copy: it plans all cargo together under hard port-draft limits, consolidates parcels
into shared voyages, times market entry against the freight-rate outlook, and proves
every plan with an independent constraint checker separate from the solver.

## Operating Context

- **Discharge ports (East Coast India):** Paradip, Visakhapatnam, Gangavaram, Gopalpur,
  Dhamra, Haldia — each with a hard maximum draft (and LOA) that caps the vessel size
  it can berth (Haldia shallow → Handysize only; Gangavaram deep → Capesize).
- **Overseas origins:** Australia, Indonesia, USA, Mozambique, Russia, each with a
  sailing time to the East Coast.
- **Vessel classes:** Handysize, Supramax, Panamax, Capesize — bigger is cheaper per
  tonne but needs deeper water.
- **Freight market:** a $/tonne rate index per vessel class per week; charter in a soft
  week rather than reactively at the deadline.
- **Horizons:** weekly and monthly plans from the same engine.
- **Workflows:** raise a cargo requirement, import cargo in bulk (CSV), reschedule a
  shipment (e.g. arriving ahead of time), cancel a shipment, and declare a port
  disruption (notify sender → reroute to the nearest feasible port) — each re-planning
  the whole schedule and writing to the audit log.

## Capabilities and Constraints

- **Optimise:** assign parcels to (vessel class, departure week) voyages minimising
  freight cost + idle capacity, honouring port draft, ship capacity, and deadlines;
  consolidate parcels into shared voyages.
- **Baseline + proof:** compare against reactive spot procurement; independent checker
  re-verifies every plan; freight-rate forecast recommends the cheapest entry week.
- **Operator edits:** manual add, CSV import (auto-validated on upload), reschedule,
  cancel, and port-disruption reroute — all persisted and audited, all re-planning.
- **Controlled access:** rank-based role hierarchy with hierarchy-filtered audit
  visibility (you see your level and below).
- **Delivery:** a Python CLI (`trackservice charter`, `charter-serve`, `charter-eval`,
  `charter-feeds`), a live server, and a self-contained static dashboard.
- **Data honesty (explicitly undecided / not to fabricate):** the freight market is
  *calibrated* to real Baltic Exchange indices but the forward weekly series is
  modelled, not a live feed; cargo demand is synthetic or CSV-fed, not yet wired to a
  live procurement/market API — that live integration is the stated next step.

## Brand Commitments

- Product name: **Charter Planner**.
- Keep the SIH problem-statement framing visible: **SIH26006 · Ministry of Steel**.
- **No AI-assistant or vendor attribution** — no tool/assistant names, and no
  co-author trailers — anywhere in the repository, commits, generated artifacts,
  or documents.

## Evidence on Hand

- **Real market anchor:** Baltic Exchange dry-bulk indices, 29 Sep 2026 — BDI 3178,
  Capesize 5103, Panamax 2390, Supramax 1797 (Handysize ~745 est.), mapped one-to-one
  to the vessel classes. Recorded in `src/trackservice/marine/data.py`.
- **Real port constraints:** representative East-Coast port draft/LOA figures.
- **Measured results (20 scenarios, all independently verified):** ~6.6% freight cost
  saved vs reactive spot, ~2.3 fewer charters, 100% cargo on time, ~88% vessel
  utilisation, solve < 0.02 s. Reproducible via `trackservice charter-eval`.
- **Sample feeds:** `data/marine_feeds/*.csv` (ports, vessels, origins, cargo demand,
  freight rates) — swap in licensed Baltic history via `freight_rates.csv`.
- **Absences future work must not fabricate:** no real client cargo history, no live
  freight feed, no rupee/dollar savings figure claimed against a real procurement book.

## Product Principles

1. **Honest caveats first.** Always distinguish real from simulated data and defensible
   from weak metrics; never overclaim a number the spread or the data can't support.
2. **Proof, not just an answer.** Every plan is checked by logic independent of the
   solver and compared against the reactive baseline it claims to beat.
3. **Controlled access is core.** Rank-based roles and a hierarchy-filtered audit trail
   are part of the product, not decoration — every action is attributable.
4. **Operator-editable and re-planning.** Add, import, reschedule, cancel, and reroute
   are first-class; each edit re-optimises and is audited.
5. **Keep the SIH framing, drop the toolmaker.** SIH26006 / Ministry of Steel stays
   visible; no AI-assistant or vendor attribution appears anywhere.
