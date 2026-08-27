"""
A self-contained HTML view of a contact graph.

Positions are sampled in Python and embedded in the page, so the result is a
single file that opens offline with no server and no network access. Stepping
through time is an index change, not a recomputation.

Two frames are used, which keeps satellites from being lost to rounding: natural
bodies are stored relative to the Sun, satellites relative to the body they
orbit. The page composes the two.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import spiceypy as sp

from ._viewer import TEMPLATE
from .bundletrace import BundleTrace

BODY_COLORS = {
    "SUN": "#ffd21e",
    "MERCURY": "#9c9187",
    "VENUS": "#e8c07a",
    "EARTH": "#3b82f6",
    "MOON": "#c8c8c8",
    "MARS": "#d1552b",
    "PHOBOS": "#8a7f76",
    "DEIMOS": "#7d736b",
    "JUPITER": "#d9a066",
    "IO": "#e6d67a",
    "EUROPA": "#dcd6c8",
    "GANYMEDE": "#9b8873",
    "CALLISTO": "#6f6257",
    "SATURN": "#e0c78a",
    "TITAN": "#d98f4a",
    "ENCELADUS": "#e8f0f2",
    "URANUS": "#7fd8de",
    "NEPTUNE": "#4257c4",
    "TRITON": "#c9bfae",
    "PLUTO": "#bda78f",
    "CHARON": "#8f8578",
}

DEFAULT_BODY_COLOR = "#8b93a1"
SATELLITE_COLOR = "#9ca3af"
SATELLITE_HIGHLIGHT = "#f472b6"
ORBIT_SAMPLES = 240
MAX_STEPS = 20000


class VisualizerError(RuntimeError):
    """Raised when a visualizer cannot be generated."""


def body_color(node) -> str:
    """The display colour for one node."""
    if getattr(node, "is_artificial", False):
        return SATELLITE_COLOR
    return BODY_COLORS.get(node.name.upper(), DEFAULT_BODY_COLOR)


def body_radius_km(node) -> float:
    """Physical radius, or zero for a satellite."""
    if getattr(node, "is_artificial", False):
        return 0.0
    try:
        return float(max(sp.bodvrd(node.name, "RADII", 3)[1]))
    except Exception:
        return 0.0


def orbit_period_s(node, et: float) -> float:
    """How long one revolution takes, seconds."""
    if getattr(node, "is_artificial", False):
        return float(node.elements.PeriodSeconds())
    mu = float(sp.bodvrd("SUN", "GM", 1)[1][0])
    state = sp.spkezr(node.name, et, "J2000", "NONE", "SUN")[0]
    return float(sp.oscltx(state, et, mu)[10])


def _positions(name: str, ets: np.ndarray, observer: str) -> np.ndarray:
    return np.asarray(sp.spkpos(name, ets, "J2000", "NONE", observer)[0], dtype=float)


def orbit_path(node, et: float) -> list[list[float]]:
    """One full revolution, relative to whatever the node orbits."""
    period = orbit_period_s(node, et)
    if not math.isfinite(period) or period <= 0:
        return []
    ets = np.linspace(et, et + period, ORBIT_SAMPLES)
    observer = node.central.name if getattr(node, "is_artificial", False) else "SUN"
    pts = _positions(node.name, ets, observer)
    return [[round(float(v), 3) for v in p] for p in pts]


def _step_times(t0: float, t1: float, step_s: float) -> np.ndarray:
    if step_s <= 0:
        raise VisualizerError(f"step_size must be positive, got {step_s!r}")
    n = int(math.floor((t1 - t0) / step_s)) + 1
    if n < 2:
        raise VisualizerError(
            f"step_size {step_s:g} s is longer than the {(t1 - t0) / 86400:.2f} d "
            "span; nothing to step through"
        )
    if n > MAX_STEPS:
        raise VisualizerError(
            f"{n:,} steps is too many to embed (limit {MAX_STEPS:,}). "
            f"Use a step_size of at least {(t1 - t0) / MAX_STEPS:,.0f} s."
        )
    return t0 + np.arange(n) * step_s


def _contacts_per_step(plan, links, times: np.ndarray) -> list[list[int]]:
    # Which links carry a contact at each sampled instant
    index = {frozenset(pair): i for i, pair in enumerate(links)}
    active: list[set[int]] = [set() for _ in times]
    for c in plan.contacts:
        i = index.get(frozenset((c.a, c.b)))
        if i is None:
            continue
        lo, hi = np.searchsorted(times, [c.start_et, c.stop_et])
        for s in range(max(0, lo - 1), min(len(times), hi + 1)):
            if c.start_et <= times[s] <= c.stop_et:
                active[s].add(i)
    return [sorted(s) for s in active]


def build_payload(
    graph,
    plan,
    step_s: float,
    *,
    trace: BundleTrace | None = None,
    title: str = "PyCG-DTN",
) -> dict:
    """Everything the page needs, as plain JSON-able data."""
    nodes = graph.GetNodes()
    if not nodes:
        raise VisualizerError("nothing to draw: add at least one body")

    t0, t1 = plan.start_et, plan.stop_et
    times = _step_times(t0, t1, step_s)

    # A satellite is stored relative to its central body, so that body has to be
    # in the payload even when it is not a node of the graph
    drawn = list(nodes)
    seen = {n.name for n in drawn}
    for node in nodes:
        central = getattr(node, "central", None)
        if central is not None and central.name not in seen:
            drawn.append(central)
            seen.add(central.name)

    node_names = {n.name for n in nodes}

    bodies = []
    for node in drawn:
        artificial = getattr(node, "is_artificial", False)
        observer = node.central.name if artificial else "SUN"
        pts = _positions(node.name, times, observer)
        bodies.append(
            {
                "name": node.name,
                "eid": getattr(node, "eid", ""),
                "kind": "satellite" if artificial else "celestial",
                "node": node.name in node_names,
                "central": node.central.name if artificial else None,
                "domain": node.domain,
                "color": body_color(node),
                "radius_km": round(body_radius_km(node), 3),
                "orbit": orbit_path(node, t0),
                "pos": [[round(float(v), 3) for v in p] for p in pts],
            }
        )

    if not any(b["name"] == "SUN" for b in bodies):
        bodies.insert(
            0,
            {
                "name": "SUN",
                "eid": "",
                "kind": "star",
                "node": False,
                "central": None,
                "domain": "sun",
                "color": BODY_COLORS["SUN"],
                "radius_km": round(body_radius_km_of("SUN"), 3),
                "orbit": [],
                "pos": [[0.0, 0.0, 0.0]] * len(times),
            },
        )

    links = [(a.name, b.name) for a, b in graph.GetLinks()]

    return {
        "meta": {
            "title": title,
            "start_utc": plan.start_utc,
            "stop_utc": plan.stop_utc,
            "step_size_s": step_s,
            "n_steps": len(times),
            "satellite_color": SATELLITE_COLOR,
            "satellite_highlight": SATELLITE_HIGHLIGHT,
        },
        "times_et": [round(float(t), 3) for t in times],
        "times_utc": [sp.et2utc(float(t), "ISOC", 0) for t in times],
        "bodies": bodies,
        "links": [{"a": a, "b": b} for a, b in links],
        "active": _contacts_per_step(plan, links, times),
        "trace": trace.AsDict() if trace is not None else None,
    }


def body_radius_km_of(name: str) -> float:
    try:
        return float(max(sp.bodvrd(name, "RADII", 3)[1]))
    except Exception:
        return 0.0


def render(payload: dict) -> str:
    """The complete HTML page for a payload."""
    data = json.dumps(payload, separators=(",", ":"))
    return TEMPLATE.replace("__TITLE__", str(payload["meta"]["title"])).replace(
        '"__PAYLOAD__"', data
    )


def write(payload: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(payload))
    return path
