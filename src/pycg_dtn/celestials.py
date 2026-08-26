"""
Celestial bodies: resolving user-supplied names against SPICE's own ID table.

Reference: NAIF Integer ID Codes
https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/naif_ids.html
"""

from __future__ import annotations

from dataclasses import dataclass, field

import spiceypy as sp

SUN_ID = 10

# Names of the nine planetary systems
SYSTEM_NAMES = {
    1: "mercury",
    2: "venus",
    3: "earth",
    4: "mars",
    5: "jupiter",
    6: "saturn",
    7: "uranus",
    8: "neptune",
    9: "pluto",
}


class UnknownCelestialBodyError(ValueError):
    """Raised when SPICE has no ID code for the requested body name."""


@dataclass(frozen=True)
class Celestial:
    """A natural body participating in the contact graph.

    ``name`` is the SPICE name upper-cased (``"MARS"``, ``"PHOBOS"``),
    ``naif_id`` its NAIF integer ID code, and ``eid`` the ION endpoint
    identifier used in the contact plan, defaulting to ``dtn:<lowercase name>``.
    """

    name: str
    naif_id: int
    eid: str = field(default="")

    def __post_init__(self) -> None:
        if not self.eid:
            object.__setattr__(self, "eid", f"dtn:{self.name.lower()}")

    @property
    def system(self) -> int:
        """
        NAIF system number

        The Sun and the barycentres belong to no planetary system, and report 0.
        """
        if self.naif_id < 100:
            return 0
        return self.naif_id // 100

    @property
    def domain(self) -> str:
        """Clock/time domain -- bodies in one planetary system share one."""
        if self.naif_id == SUN_ID:
            return "sun"
        return SYSTEM_NAMES.get(self.system, f"system{self.system}")

    @property
    def is_planet(self) -> bool:
        """True for the ``N99`` codes"""
        return self.naif_id >= 100 and self.naif_id % 100 == 99

    def __str__(self) -> str: 
        return self.name


def resolve(name: str, *, eid: str | None = None) -> Celestial:
    """Look up one body by name, or by its integer NAIF code given as a string.

    Raises:
        UnknownCelestialBodyError: If SPICE has no entry for the name or code.
    """
    key = name.strip() if isinstance(name, str) else str(name)
    if not key:
        raise UnknownCelestialBodyError("empty celestial body name")

    try:
        naif_id = int(key)
    except ValueError:
        canonical = key.upper()
        try:
            naif_id = sp.bodn2c(canonical)
        except Exception as exc:
            raise UnknownCelestialBodyError(
                f"SPICE has no ID code for the celestial body {name!r}. "
                "Check the spelling, or use AddSatellite() if this is an "
                "artificial spacecraft."
            ) from exc
    else:
        try:
            canonical = sp.bodc2n(naif_id).upper()
        except Exception as exc:
            raise UnknownCelestialBodyError(
                f"SPICE has no name for the NAIF ID code {naif_id}."
            ) from exc

    return Celestial(name=canonical, naif_id=naif_id, eid=eid or "")
