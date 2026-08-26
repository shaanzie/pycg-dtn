"""
LOS Calculations done here

occultation
    A third body sits between them.  Mars hides Phobos, Jupiter hides Io.

solar conjunction
    The signal path passes close to the Sun.  
    "Close" is measured as the Sun-Earth-probe angle; below roughly 3 degrees
    the link is treated as unusable.

Both are computed with SPICE's geometry-finder routines.
"""

from __future__ import annotations

import math

import numpy as np
import spiceypy as sp
from spiceypy.utils.callbacks import SpiceUDFUNB, SpiceUDFUNS

from .celestials import Celestial

AU_KM = 1.495978707e8

def window(start: float, stop: float):
    # A SPICE window holding the single interval in seconds ET.
    cell = sp.cell_double(2)
    sp.wninsd(start, stop, cell)
    return cell


def window_intervals(w) -> list[tuple[float, float]]:
    # Unpack a SPICE window into a list of (start, stop) pairs.
    return [tuple(map(float, sp.wnfetd(w, i))) for i in range(sp.wncard(w))]


def window_total(w) -> float:
    # Total measure of a SPICE window, seconds.
    return sum(float(np.diff(sp.wnfetd(w, i))[0]) for i in range(sp.wncard(w)))


def max_radius(body: Celestial) -> float:
    if getattr(body, "is_artificial", False):
        return 0.0
    return float(max(sp.bodvrd(body.name, "RADII", 3)[1]))



def _positive(name: str, value: float) -> float:
    value = float(value)
    if not np.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be a positive, finite number, got {value!r}")
    return value


class GeometryConfig:
    # Search steps and exclusion thresholds for the visibility computation.
    __slots__ = (
        "_occult_step_s",
        "_corona_step_s",
        "_prefilter_step_s",
        "_prefilter_radii_margin",
        "_sep_exclusion_deg",
        "_rate_sample_s",
        "_rate_tolerance",
    )

    def __init__(
        self,
        *,
        occult_step_s: float = 600.0,
        corona_step_s: float = 6 * 3600.0,
        prefilter_step_s: float = 1800.0,
        prefilter_radii_margin: float = 3.0,
        sep_exclusion_deg: float = 3.0,
        rate_sample_s: float = 3600.0,
        rate_tolerance: float = 0.10,
    ) -> None:
        self._occult_step_s = _positive("occult_step_s", occult_step_s)
        self._corona_step_s = _positive("corona_step_s", corona_step_s)
        self._prefilter_step_s = _positive("prefilter_step_s", prefilter_step_s)
        self._prefilter_radii_margin = _positive(
            "prefilter_radii_margin", prefilter_radii_margin
        )
        self._sep_exclusion_deg = _positive("sep_exclusion_deg", sep_exclusion_deg)
        self._rate_sample_s = _positive("rate_sample_s", rate_sample_s)
        self._rate_tolerance = _positive("rate_tolerance", rate_tolerance)

    def GetOccultStep(self) -> float:
        # Occultation search step, seconds.
        return self._occult_step_s

    def SetOccultStep(self, seconds: float) -> GeometryConfig:
        # Set the occultation search step.
        self._occult_step_s = _positive("occult_step_s", seconds)
        return self

    def GetCoronaStep(self) -> float:
        # Solar-conjunction search step, seconds.
        return self._corona_step_s

    def SetCoronaStep(self, seconds: float) -> GeometryConfig:
        # Set the solar-conjunction search step
        self._corona_step_s = _positive("corona_step_s", seconds)
        return self

    def GetPrefilterStep(self) -> float:
        # Sampling step for the cheap occulter prefilter, seconds.
        return self._prefilter_step_s

    def SetPrefilterStep(self, seconds: float) -> GeometryConfig:
        # Set the prefilter sampling step.
        self._prefilter_step_s = _positive("prefilter_step_s", seconds)
        return self

    def GetPrefilterMargin(self) -> float:
        # Prefilter keep-radius, in multiples of the occulter's own radius.
        return self._prefilter_radii_margin

    def SetPrefilterMargin(self, multiples: float) -> GeometryConfig:
        # Set how close a body must come to a link before it is treated as a
        # plausible occulter.
        self._prefilter_radii_margin = _positive("prefilter_radii_margin", multiples)
        return self

    def GetSepExclusion(self) -> float:
        # Sun-Earth-probe exclusion angle, degrees.
        return self._sep_exclusion_deg

    def SetSepExclusion(self, degrees: float) -> GeometryConfig:
        # Set the solar exclusion angle in degrees.  DSN practice treats links
        # inside about 3 degrees as unusable.
        self._sep_exclusion_deg = _positive("sep_exclusion_deg", degrees)
        return self

    def GetCoronaExclusionKm(self) -> float:
        # The exclusion angle expressed as a miss distance from the Sun, km.
        return AU_KM * math.sin(math.radians(self._sep_exclusion_deg))

    def GetRateSample(self) -> float:
        # Spacing at which range and rate are sampled inside a contact, seconds.
        return self._rate_sample_s

    def SetRateSample(self, seconds: float) -> GeometryConfig:
        # Set the in-contact rate sampling interval.
        self._rate_sample_s = _positive("rate_sample_s", seconds)
        return self

    def GetRateTolerance(self) -> float:
        # Fractional rate drift tolerated before a contact is split.
        return self._rate_tolerance

    def SetRateTolerance(self, fraction: float) -> GeometryConfig:
        # Set how far the data rate may drift within one sub-contact before it
        # is cut, as a fraction
        self._rate_tolerance = _positive("rate_tolerance", fraction)
        return self

    def AsDict(self) -> dict[str, float]:
        # All parameters, for embedding in output metadata.
        return {
            "occult_step_s": self._occult_step_s,
            "corona_step_s": self._corona_step_s,
            "prefilter_step_s": self._prefilter_step_s,
            "prefilter_radii_margin": self._prefilter_radii_margin,
            "sep_exclusion_deg": self._sep_exclusion_deg,
            "corona_exclusion_km": self.GetCoronaExclusionKm(),
            "rate_sample_s": self._rate_sample_s,
            "rate_tolerance": self._rate_tolerance,
        }


def segment_distances(
    p_a: np.ndarray, p_b: np.ndarray, p_c: np.ndarray
) -> np.ndarray:
    # Distance from point C to the segment A->B, vectorised over many epochs.
    d = p_b - p_a
    ac = p_c - p_a
    denom = np.einsum("ij,ij->i", d, d)
    t = np.clip(np.einsum("ij,ij->i", ac, d) / denom, 0.0, 1.0)
    return np.linalg.norm(ac - t[:, None] * d, axis=1)


def prefilter_occulters(
    bodies: list[Celestial],
    links: list[tuple[Celestial, Celestial]],
    t0: float,
    t1: float,
    config: GeometryConfig,
) -> dict[tuple[str, str], list[Celestial]]:
    # Cheaply rule out (link, blocker) combinations that can never occult.
    ets = np.arange(t0, t1, config.GetPrefilterStep())
    pos = {
        b.name: np.asarray(
            sp.spkpos(b.name, ets, "J2000", "NONE", "SUN")[0], dtype=float
        )
        for b in bodies
    }
    radii = {b.name: max_radius(b) for b in bodies}
    margin = config.GetPrefilterMargin()

    keep: dict[tuple[str, str], list[Celestial]] = {}
    for a, b in links:
        candidates = []
        for c in bodies:
            if c.name in (a.name, b.name):
                continue
            dmin = segment_distances(pos[a.name], pos[b.name], pos[c.name]).min()
            if dmin < margin * radii[c.name]:
                candidates.append(c)
        keep[(a.name, b.name)] = candidates
    return keep


def occultation_window(
    a: Celestial, b: Celestial, occulter: Celestial, cnfine, config: GeometryConfig
):
    # Times within ``cnfine`` when ``occulter`` hides ``b`` from ``a``.
    return sp.gfoclt(
        "ANY",
        occulter.name,
        "ELLIPSOID",
        f"IAU_{occulter.name}",
        b.name,
        "POINT",
        " ",
        "LT",
        a.name,
        config.GetOccultStep(),
        cnfine,
        sp.cell_double(20000),
    )


def corona_window(a: Celestial, b: Celestial, cnfine, config: GeometryConfig):
    # Times within ``cnfine`` when the a->b path passes too close to the Sun.
    threshold = config.GetCoronaExclusionKm()

    def closest_solar_approach(et: float) -> float:
        pa = np.asarray(sp.spkpos(a.name, et, "J2000", "NONE", "SUN")[0], dtype=float)
        pb = np.asarray(sp.spkpos(b.name, et, "J2000", "NONE", "SUN")[0], dtype=float)
        d = pb - pa
        t = float(np.clip(-pa.dot(d) / d.dot(d), 0.0, 1.0))
        return float(np.linalg.norm(pa + t * d))

    udf = SpiceUDFUNS(closest_solar_approach)
    udq = SpiceUDFUNB(lambda f, et: sp.uddc(f, et, 60.0))
    result = sp.gfuds(
        udf,
        udq,
        "<",
        threshold,
        0.0,
        config.GetCoronaStep(),
        2000,
        cnfine,
        sp.cell_double(4000),
    )
    del udf, udq
    return result
