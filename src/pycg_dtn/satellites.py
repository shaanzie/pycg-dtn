"""
Artificial satellites, defined by classical Keplerian elements and propagated as
a two-body orbit about a central body.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import spiceypy as sp

from .celestials import Celestial, UnknownCelestialBodyError, resolve

_SYNTHETIC_ID_BASE = -900000


class SatelliteError(ValueError):
    """Raised for malformed orbital elements, or an unusable central body."""


@dataclass(frozen=True)
class KeplerianElements:
    """A classical two-body orbit about ``central``."""

    

    central: str
    semi_major_axis_km: float
    eccentricity: float = 0.0
    inclination_deg: float = 0.0
    raan_deg: float = 0.0
    arg_periapsis_deg: float = 0.0
    mean_anomaly_deg: float = 0.0
    epoch_utc: str = "2026-01-01T00:00:00"

    def __post_init__(self) -> None:
        if not math.isfinite(self.semi_major_axis_km) or self.semi_major_axis_km <= 0:
            raise SatelliteError(
                f"semi_major_axis_km must be positive, got {self.semi_major_axis_km!r}"
            )
        if not 0.0 <= self.eccentricity < 1.0:
            raise SatelliteError(
                "eccentricity must be in [0, 1); an open orbit never returns. "
                f"Got {self.eccentricity!r}"
            )
        if not 0.0 <= self.inclination_deg <= 180.0:
            raise SatelliteError(
                f"inclination_deg must be in [0, 180], got {self.inclination_deg!r}"
            )

    @property
    def periapsis_km(self) -> float:
        return self.semi_major_axis_km * (1.0 - self.eccentricity)

    @property
    def apoapsis_km(self) -> float:
        return self.semi_major_axis_km * (1.0 + self.eccentricity)

    def CentralBody(self) -> Celestial:
        try:
            return resolve(self.central)
        except UnknownCelestialBodyError as exc:
            raise SatelliteError(
                f"unknown central body {self.central!r} for the orbit"
            ) from exc

    def GravitationalParameter(self) -> float:
        """km^3/s^2, from gm_de440.tpc, which must already be loaded"""
        body = self.CentralBody()
        try:
            return float(sp.bodvrd(body.name, "GM", 1)[1][0])
        except Exception as exc:
            raise SatelliteError(
                f"no GM available for {body.name}; gm_de440.tpc must be loaded "
                "before an orbit can be propagated"
            ) from exc

    def PeriodSeconds(self) -> float:
        mu = self.GravitationalParameter()
        return 2.0 * math.pi * math.sqrt(self.semi_major_axis_km**3 / mu)

    def CheckClearsSurface(self) -> None:
        body = self.CentralBody()
        try:
            radius = float(max(sp.bodvrd(body.name, "RADII", 3)[1]))
        except Exception:
            return
        if self.periapsis_km <= radius:
            raise SatelliteError(
                f"periapsis {self.periapsis_km:,.1f} km is inside {body.name} "
                f"(radius {radius:,.1f} km); the orbit intersects the surface"
            )

    def AsConicArray(self, epoch_et: float, mu: float) -> list[float]:
        return [
            self.periapsis_km,
            self.eccentricity,
            math.radians(self.inclination_deg),
            math.radians(self.raan_deg),
            math.radians(self.arg_periapsis_deg),
            math.radians(self.mean_anomaly_deg),
            epoch_et,
            mu,
        ]

    def AsDict(self) -> dict[str, float | str]:
        return {
            "central": self.central,
            "semi_major_axis_km": self.semi_major_axis_km,
            "eccentricity": self.eccentricity,
            "inclination_deg": self.inclination_deg,
            "raan_deg": self.raan_deg,
            "arg_periapsis_deg": self.arg_periapsis_deg,
            "mean_anomaly_deg": self.mean_anomaly_deg,
            "epoch_utc": self.epoch_utc,
        }


@dataclass(frozen=True)
class Satellite:
    """An artificial body in the contact graph, propagated from ``elements``."""


    name: str
    naif_id: int
    central: Celestial
    elements: KeplerianElements
    eid: str = field(default="")

    def __post_init__(self) -> None:
        if not self.eid:
            slug = self.name.lower().replace(" ", "-").replace("_", "-")
            object.__setattr__(self, "eid", f"dtn:{slug}")

    is_artificial = True
    is_planet = False

    @property
    def system(self) -> int:
        return self.central.system

    @property
    def domain(self) -> str:
        return self.central.domain

    def __str__(self) -> str:
        return self.name


def synthetic_id(index: int) -> int:
    return _SYNTHETIC_ID_BASE - index
