"""PyCG-DTN
    build DTN contact graphs for deep-space networks from SPICE.
"""

from __future__ import annotations

from .celestials import Celestial, UnknownCelestialBodyError, resolve
from .geometry import GeometryConfig
from .graph import ContactGraph, ContactGraphError
from .kernels import Kernel, KernelError
from .linkbudget import C_KM_S, LinkBudget
from .plan import Contact, ContactPlan, LinkSummary
from .satellites import KeplerianElements, Satellite, SatelliteError

__version__ = "1.0.0"

__all__ = [
    "C_KM_S",
    "Celestial",
    "Contact",
    "ContactGraph",
    "ContactGraphError",
    "ContactPlan",
    "GeometryConfig",
    "KeplerianElements",
    "Kernel",
    "KernelError",
    "LinkBudget",
    "LinkSummary",
    "Satellite",
    "SatelliteError",
    "UnknownCelestialBodyError",
    "__version__",
    "resolve",
]
