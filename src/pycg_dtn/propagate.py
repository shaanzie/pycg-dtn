"""
Turning orbital elements into an ephemeris SPICE can read.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np
import spiceypy as sp

from .satellites import Satellite, SatelliteError

COVERAGE_PAD_S = 86400.0
STATES_PER_ORBIT = 8
_MIN_STATES = 2
_MAX_STATES = 200_000


def _sample_epochs(sat: Satellite, t0: float, t1: float) -> np.ndarray:
    period = sat.elements.PeriodSeconds()
    lo, hi = t0 - COVERAGE_PAD_S, t1 + COVERAGE_PAD_S
    n = int(np.ceil((hi - lo) / (period / STATES_PER_ORBIT))) + 1
    return np.linspace(lo, hi, max(_MIN_STATES, min(n, _MAX_STATES)))


def write_spk(sat: Satellite, t0: float, t1: float, path: str | Path) -> Path:
    """Propagate sat across [t0, t1] and write it as a type 5 SPK."""
    if t1 <= t0:
        raise SatelliteError(f"empty span for {sat.name}: {t0} -> {t1}")

    elements = sat.elements
    elements.CheckClearsSurface()
    mu = elements.GravitationalParameter()
    conic = elements.AsConicArray(sp.str2et(elements.epoch_utc), mu)

    epochs = _sample_epochs(sat, t0, t1)
    states = np.array([sp.conics(conic, float(et)) for et in epochs])

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    handle = sp.spkopn(str(path), f"pycg-dtn {sat.name}", 0)
    try:
        sp.spkw05(
            handle,
            sat.naif_id,
            sat.central.naif_id,
            "J2000",
            float(epochs[0]),
            float(epochs[-1]),
            f"{sat.name} two-body",
            mu,
            len(epochs),
            states,
            epochs,
        )
    finally:
        sp.spkcls(handle)

    return path


class SatelliteEphemerides:
    """Scratch SPKs for a set of satellites"""

    def __init__(self, satellites: list[Satellite]) -> None:
        self._satellites = list(satellites)
        self._dir: Path | None = None
        self._paths: dict[str, Path] = {}

    def Build(self, t0: float, t1: float) -> dict[str, Path]:
        self.Cleanup()
        self._dir = Path(tempfile.mkdtemp(prefix="pycg-spk-"))
        for sat in self._satellites:
            slug = sat.name.lower().replace(" ", "_").replace("-", "_")
            path = write_spk(sat, t0, t1, self._dir / f"{slug}.bsp")
            sp.furnsh(str(path))
            sp.boddef(sat.name, sat.naif_id)
            self._paths[sat.name] = path
        return dict(self._paths)

    def Cleanup(self) -> None:
        for path in self._paths.values():
            try:
                sp.unload(str(path))
            except Exception:
                pass
        self._paths.clear()
        if self._dir and self._dir.exists():
            shutil.rmtree(self._dir, ignore_errors=True)
        self._dir = None

    def __enter__(self) -> SatelliteEphemerides:
        return self

    def __exit__(self, *exc) -> None:
        self.Cleanup()
