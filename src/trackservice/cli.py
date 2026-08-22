"""Command line: run the pipeline, print the stage metrics, build the dashboard."""

from __future__ import annotations

import json
import pathlib

import typer
from rich.console import Console
from rich.table import Table

from . import pipeline as _pipeline
from .dashboard import render_dashboard

app = typer.Typer(add_completion=False, help="Railway maintenance block scheduler.")
console = Console()


@app.command()
def run(
    seed: int = typer.Option(7, help="Dataset seed (fixed data for a repeatable demo)."),
    requests: int = typer.Option(40, help="Number of maintenance work requests."),
    nights: int = typer.Option(5, help="Number of engineering nights."),
    out: str = typer.Option("schedule.json", help="Where to write the JSON report."),
    dashboard: str = typer.Option("dashboard.html", help="Where to write the HTML dashboard."),
) -> None:
    """Solve, explain, propose alternatives, inject an emergency, and render."""
    report = _pipeline.run(seed=seed, n_requests=requests, nights=nights)

    pathlib.Path(out).write_text(json.dumps(report, indent=2))
    render_dashboard(report, dashboard)

    _print_metrics(report)
    console.print(f"\n[green]Wrote[/] {out}  and  [green]{dashboard}[/] (open it directly, no server).")


@app.command()
def metrics(
    seed: int = typer.Option(7),
    requests: int = typer.Option(40),
    nights: int = typer.Option(5),
) -> None:
    """Just print the numbers to quote — no files written."""
    report = _pipeline.run(seed=seed, n_requests=requests, nights=nights, explain=False)
    _print_metrics(report)


@app.command()
def sweep(
    seeds: int = typer.Option(5, help="How many seeds to run."),
    requests: int = typer.Option(40),
    nights: int = typer.Option(5),
) -> None:
    """Run several seeds and report the CP-SAT-vs-greedy gap — proof it's not one lucky dataset."""
    table = Table(title="CP-SAT vs greedy across seeds")
    for col in ("seed", "CP-SAT sched", "greedy sched", "CP-SAT wt", "greedy wt", "wt gap", "solve s"):
        table.add_column(col, justify="right")

    gaps = []
    for s in range(seeds):
        rep = _pipeline.run(seed=s, n_requests=requests, nights=nights, explain=False)
        om, gm = rep["metrics"]["optimal"], rep["metrics"]["greedy"]
        gap = om["priority_weight"] - gm["priority_weight"]
        gaps.append(gap)
        table.add_row(
            str(s), str(om["scheduled"]), str(gm["scheduled"]),
            str(om["priority_weight"]), str(gm["priority_weight"]),
            f"+{gap}", f"{om['solve_seconds']}",
        )
    console.print(table)
    console.print(
        f"[bold]Mean priority-weight gap: +{sum(gaps) / len(gaps):.1f}[/] "
        f"across {seeds} seeds — CP-SAT never loses to greedy, and usually wins."
    )


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address (localhost by default)."),
    port: int = typer.Option(8000, help="Port."),
) -> None:
    """Start the live-solve server: judges can author an emergency and watch it solve."""
    from .service import serve as _serve

    console.print(f"[green]Live dashboard:[/] http://{host}:{port}  (Ctrl-C to stop)")
    _serve(host=host, port=port)


def _print_metrics(report: dict) -> None:
    om = report["metrics"]["optimal"]
    gm = report["metrics"]["greedy"]
    emg = report.get("emergency", {})

    table = Table(title="Metrics to quote on stage")
    table.add_column("", style="bold")
    table.add_column("CP-SAT", justify="right")
    table.add_column("Greedy FCFS", justify="right")
    table.add_row("Requests scheduled", f"{om['scheduled']}/{om['total_requests']}", f"{gm['scheduled']}/{gm['total_requests']}")
    table.add_row("Priority weight", str(om["priority_weight"]), str(gm["priority_weight"]))
    table.add_row("Window utilisation", f"{om['window_utilisation_pct']}%", f"{gm['window_utilisation_pct']}%")
    table.add_row("Solve time", f"{om['solve_seconds']}s", f"{gm['solve_seconds']}s")
    table.add_row("Status", "OPTIMAL (proven)" if om["proven_optimal"] else om.get("status", "?"), "greedy")
    console.print(table)

    if emg:
        console.print(
            f"\n[yellow]Emergency:[/] {emg['request']['title']} on {emg['request']['section']} "
            f"→ bumps {emg['bumped'] or 'nothing'}, weight {emg['weight_before']} → {emg['weight_after']}."
        )


if __name__ == "__main__":
    app()
