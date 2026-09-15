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
from .orbital_id import (
    BP_VERSION,
    REGIME_BODY,
    REGIME_SATELLITE,
    SCHEME_VERSION,
    BuildEid,
)
from .plan import Contact, ContactPlan, LinkSummary
from .satellites import KeplerianElements, Satellite, SatelliteError
from .visualize import VisualizerError

__version__ = "1.6.0"

__all__ = [
    "VisualizerError",
    "Hop",
    "BP_VERSION",
    "BuildEid",
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
    "KeplerianElements",
    "Kernel",
    "KernelError",
    "LinkBudget",
    "LinkSummary",
    "REGIME_BODY",
    "REGIME_SATELLITE",
    "SCHEME_VERSION",
    "Satellite",
    "SatelliteError",
    "UnknownCelestialBodyError",
    "__version__",
    "resolve",
]
