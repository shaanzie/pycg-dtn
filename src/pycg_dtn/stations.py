"""
Ground stations: fixed sites on the surface of a body, turning with it.

A station's position is constant in its body's IAU body-fixed frame, so it is
written to SPICE as an SPK segment in that frame and SPICE rotates it with the
body. This is how NAIF's own DSN station kernels work:
https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/stations/

What a station can see is limited by an elevation mask above its local horizon.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import spiceypy as sp

from .celestials import Celestial

_STATION_ID_BASE = -800000


class GroundStationError(ValueError):
    """Raised for an impossible site, or an unusable host body."""


@dataclass(frozen=True)
class GroundStation:
    """A node fixed on the surface of ``central``.

    Latitude is geodetic and longitude is east-positive, both in degrees, in
    the body's IAU frame. ``min_elevation_deg`` is the elevation mask: targets
    below it are not visible.
    """

    name: str
    naif_id: int
    central: Celestial
    latitude_deg: float
    longitude_deg: float
    altitude_km: float = 0.0
    min_elevation_deg: float = 0.0
    eid: str = field(default="")

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude_deg <= 90.0:
            raise GroundStationError(
                f"{self.name}: latitude_deg must be in [-90, 90], "
                f"got {self.latitude_deg!r}"
            )
        if not math.isfinite(self.longitude_deg):
            raise GroundStationError(
                f"{self.name}: longitude_deg must be finite, got {self.longitude_deg!r}"
            )
        if not math.isfinite(self.altitude_km):
            raise GroundStationError(
                f"{self.name}: altitude_km must be finite, got {self.altitude_km!r}"
            )
        if not -90.0 <= self.min_elevation_deg < 90.0:
            raise GroundStationError(
                f"{self.name}: min_elevation_deg must be in [-90, 90), "
                f"got {self.min_elevation_deg!r}"
            )
        if not self.eid:
            slug = self.name.lower().replace(" ", "-").replace("_", "-")
            object.__setattr__(self, "eid", f"dtn:{slug}")

    is_artificial = True
    is_planet = False
    is_station = True

    @property
    def system(self) -> int:
        return self.central.system

    @property
    def domain(self) -> str:
        return self.central.domain

    def BodyFrame(self) -> str:
        """The body-fixed frame the site is fixed in."""
        return f"IAU_{self.central.name}"

    def BodyFixedPosition(self) -> np.ndarray:
        """Site position in the body-fixed frame, km. Needs the PCK loaded."""
        try:
            radii = sp.bodvrd(self.central.name, "RADII", 3)[1]
        except Exception as exc:
            raise GroundStationError(
                f"{self.name}: no radii for {self.central.name}; "
                "pck00011.tpc must be loaded"
            ) from exc
        equatorial = float(radii[0])
        polar = float(radii[2])
        flattening = (equatorial - polar) / equatorial
        return np.asarray(
            sp.georec(
                math.radians(self.longitude_deg),
                math.radians(self.latitude_deg),
                self.altitude_km,
                equatorial,
                flattening,
            ),
            dtype=float,
        )

    def LocalUp(self) -> np.ndarray:
        """Unit vector along the local vertical (geodetic), body-fixed frame."""
        lat = math.radians(self.latitude_deg)
        lon = math.radians(self.longitude_deg)
        return np.array(
            [math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)]
        )

    def AsDict(self) -> dict[str, float | str]:
        return {
            "central": self.central.name,
            "latitude_deg": self.latitude_deg,
            "longitude_deg": self.longitude_deg,
            "altitude_km": self.altitude_km,
            "min_elevation_deg": self.min_elevation_deg,
        }

    def __str__(self) -> str:
        return self.name


def station_id(index: int) -> int:
    return _STATION_ID_BASE - index
