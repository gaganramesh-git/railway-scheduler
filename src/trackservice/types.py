"""Core domain types.

TIME UNITS — read this before touching anything else.

Every time quantity in this package is an integer count of **half-hour ticks**.
Windows, durations, starts, ends, duty-hour budgets: all ticks, everywhere, with
no exceptions. Hours only ever appear at the edges — in the data generator that
authors the fixtures, and in the formatters that render for humans.

This is deliberate. Mixing raw hours into a model whose window bounds are in
ticks produces a schedule that solves cleanly and silently ignores its own
resource limits: intervals are half their true length, so twice as many fit
under a cumulative capacity. Nothing errors. The bug is invisible until someone
checks whether the crew counts were ever really respected.

Convert at the boundary with `hours_to_ticks`, and never in the middle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

TICKS_PER_HOUR = 2


def hours_to_ticks(hours: float) -> int:
    """Convert hours to half-hour ticks. Only for use at the data boundary."""
    ticks = hours * TICKS_PER_HOUR
    if abs(ticks - round(ticks)) > 1e-9:
        raise ValueError(f"{hours}h is not a whole number of half-hour ticks")
    return int(round(ticks))


def ticks_to_hours(ticks: int) -> float:
    return ticks / TICKS_PER_HOUR


def format_clock(tick: int) -> str:
    """Render an absolute tick as a wall-clock time, where tick 0 is 22:00."""
    minutes = 22 * 60 + tick * 30
    return f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"


class CrewType(str, Enum):
    """Departments that hold their own crews. Work needs one type; they don't substitute."""

    PWAY = "p-way"          # permanent way: track, ballast, tamping
    SIGNAL = "signalling"   # signalling and interlocking
    OHE = "ohe"             # overhead electrification
    BRIDGE = "bridge"       # structures and bridge inspection


class Equipment(str, Enum):
    """Machines held in a divisional pool. Scarcer than crews; usually the true bottleneck."""

    TAMPER = "tamping-machine"
    BALLAST_CLEANER = "ballast-cleaner"
    RAIL_GRINDER = "rail-grinder"
    TOWER_WAGON = "tower-wagon"
    ROAD_RAILER = "road-railer"
    NONE = "none"


class Priority(int, Enum):
    """Weight carried into the objective. Safety-critical work outranks routine work."""

    ROUTINE = 3
    IMPORTANT = 4
    URGENT = 5


@dataclass(frozen=True)
class Section:
    """A stretch of track that can be blocked to traffic as one unit."""

    id: str
    name: str
    traffic_density: int  # trains/night displaced by a block here; drives disruption cost


@dataclass(frozen=True)
class Window:
    """An engineering block granted on one section for one night.

    `start` and `end` are absolute ticks within the night, measured from 22:00.
    A section with no Window on a night simply cannot be worked that night.
    """

    section_id: str
    night: int
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class Request:
    """One maintenance job somebody wants a block for."""

    id: str
    title: str
    section_id: str
    duration: int          # ticks
    priority: Priority
    crew: CrewType
    crew_size: int         # concurrent gangs drawn from the crew pool
    equipment: Equipment
    earliest_night: int
    latest_night: int      # inclusive deadline; work refused after this is a safety liability
    is_emergency: bool = False

    def nights(self) -> range:
        return range(self.earliest_night, self.latest_night + 1)


@dataclass(frozen=True)
class ResourcePool:
    """What the division actually has available, per night.

    `crew_shift` is the duty-hour ceiling: one gang may not be booked for more
    than this many ticks in a night, so total booked crew-ticks of a type cannot
    exceed `crew[type] * crew_shift`.
    """

    crew: dict[CrewType, int]
    equipment: dict[Equipment, int]
    crew_shift: int

    def crew_capacity(self, crew: CrewType) -> int:
        return self.crew.get(crew, 0)

    def equipment_capacity(self, item: Equipment) -> int:
        if item is Equipment.NONE:
            return 10_000  # "no machine needed" must never bind
        return self.equipment.get(item, 0)


@dataclass(frozen=True)
class Scenario:
    """A complete problem instance: what to do, where it can go, and with what."""

    sections: list[Section]
    windows: list[Window]
    requests: list[Request]
    pool: ResourcePool
    nights: int
    seed: int = 0

    def window(self, section_id: str, night: int) -> Window | None:
        for w in self.windows:
            if w.section_id == section_id and w.night == night:
                return w
        return None

    def request(self, request_id: str) -> Request:
        for r in self.requests:
            if r.id == request_id:
                return r
        raise KeyError(request_id)

    def with_request(self, extra: Request) -> Scenario:
        """A copy with one more request — used to inject an emergency mid-demo."""
        return Scenario(
            sections=self.sections,
            windows=self.windows,
            requests=[*self.requests, extra],
            pool=self.pool,
            nights=self.nights,
            seed=self.seed,
        )


@dataclass(frozen=True)
class Assignment:
    """A request placed on a night at a time."""

    request_id: str
    night: int
    start: int
    end: int

    @property
    def duration(self) -> int:
        return self.end - self.start


@dataclass
class Schedule:
    """The result of a solve: what got placed, what didn't, and how it went."""

    assignments: list[Assignment] = field(default_factory=list)
    unscheduled: list[str] = field(default_factory=list)
    status: str = "UNKNOWN"
    objective: int = 0
    solve_seconds: float = 0.0
    proven_optimal: bool = False

    def by_night(self, night: int) -> list[Assignment]:
        return sorted(
            (a for a in self.assignments if a.night == night),
            key=lambda a: a.start,
        )

    def assignment(self, request_id: str) -> Assignment | None:
        for a in self.assignments:
            if a.request_id == request_id:
                return a
        return None

    @property
    def scheduled_ids(self) -> set[str]:
        return {a.request_id for a in self.assignments}
