"""PyCG-DTN
    build DTN contact graphs for deep-space networks from SPICE.
"""

from __future__ import annotations

from .bundletrace import Bundle, BundleTrace, BundleTraceError, Hop
from .celestials import Celestial, UnknownCelestialBodyError, resolve
from .geometry import GeometryConfig
from .graph import ContactGraph, ContactGraphError
from .kernels import Kernel, KernelError
from .linkbudget import C_KM_S, LinkBudget
from .plan import Contact, ContactPlan, LinkSummary
from .satellites import KeplerianElements, Satellite, SatelliteError
from .stations import GroundStation, GroundStationError
from .visualize import VisualizerError

__version__ = "2.0.0"

__all__ = [
    "VisualizerError",
    "Hop",
    "BundleTraceError",
    "BundleTrace",
    "Bundle",
    "C_KM_S",
    "Celestial",
    "Contact",
    "ContactGraph",
    "ContactGraphError",
    "ContactPlan",
    "GeometryConfig",
    "GroundStation",
    "GroundStationError",
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
