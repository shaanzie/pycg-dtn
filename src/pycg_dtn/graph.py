"""The builder: add nodes, then generate the contact graph over them.
"""

from __future__ import annotations

import time
from itertools import combinations
from pathlib import Path

import numpy as np
import spiceypy as sp

from . import geometry as geo
from . import kernels as kern
from .celestials import Celestial, UnknownCelestialBodyError, resolve
from .geometry import GeometryConfig
from .linkbudget import C_KM_S, LinkBudget
from .plan import Contact, ContactPlan, LinkSummary
from .propagate import SatelliteEphemerides
from .satellites import (
    KeplerianElements,
    Satellite,
    SatelliteError,
    synthetic_id,
)

DEFAULT_START_UTC = "2026-01-01T00:00:00"


class ContactGraphError(RuntimeError):
    # Raised when the graph is not in a state that can be generated from.
    pass


class ContactGraph:
    # A scenario under construction: its nodes, its radio, its geometry.
    def __init__(
        self,
        *,
        kernel_dir: str | Path | None = None,
        link_budget: LinkBudget | None = None,
        geometry: GeometryConfig | None = None,
    ) -> None:
        self._celestials: list[Celestial] = []
        self._satellites: list = []
        self._kernel_dir = Path(kernel_dir) if kernel_dir else Path.cwd() / "kernels"
        self._link_budget = link_budget or LinkBudget()
        self._geometry = geometry or GeometryConfig()
        self._furnished = False

    def AddCelestial(self, name: str, *, eid: str | None = None) -> Celestial:
        # Add a natural body, a planet, a moon, or the Sun as a node.
        body = resolve(name, eid=eid)

        for existing in self._celestials:
            if existing.naif_id == body.naif_id:
                raise UnknownCelestialBodyError(
                    f"{name!r} is already in the graph as {existing.name} "
                    f"(NAIF {existing.naif_id})"
                )

        self._celestials.append(body)
        return body

    def AddSatellite(
        self,
        name: str,
        central: str,
        *,
        semi_major_axis_km: float | None = None,
        altitude_km: float | None = None,
        eccentricity: float = 0.0,
        inclination_deg: float = 0.0,
        raan_deg: float = 0.0,
        arg_periapsis_deg: float = 0.0,
        mean_anomaly_deg: float = 0.0,
        epoch_utc: str = DEFAULT_START_UTC,
        eid: str | None = None,
    ) -> Satellite:
        # Add an artificial satellite orbiting central.
        if (semi_major_axis_km is None) == (altitude_km is None):
            raise SatelliteError(
                f"{name}: give exactly one of semi_major_axis_km or altitude_km"
            )

        for existing in self._satellites:
            if existing.name.upper() == name.upper():
                raise SatelliteError(f"{name!r} is already in the graph")

        body = resolve(central)

        if altitude_km is not None:
            radius = self._EquatorialRadius(body)
            semi_major_axis_km = (radius + altitude_km) / (1.0 - eccentricity)

        elements = KeplerianElements(
            central=body.name,
            semi_major_axis_km=semi_major_axis_km,
            eccentricity=eccentricity,
            inclination_deg=inclination_deg,
            raan_deg=raan_deg,
            arg_periapsis_deg=arg_periapsis_deg,
            mean_anomaly_deg=mean_anomaly_deg,
            epoch_utc=epoch_utc,
        )
        sat = Satellite(
            name=name.upper(),
            naif_id=synthetic_id(len(self._satellites)),
            central=body,
            elements=elements,
            eid=eid or "",
        )
        self._satellites.append(sat)
        self._furnished = False
        return sat

    def _EquatorialRadius(self, body: Celestial) -> float:
        try:
            return float(max(sp.bodvrd(body.name, "RADII", 3)[1]))
        except Exception:
            small = [kern.LSK, kern.PCK]
            kern.fetch(small, self._kernel_dir, progress=False)
            kern.furnish(small, self._kernel_dir)
            return float(max(sp.bodvrd(body.name, "RADII", 3)[1]))

    def GetCelestials(self) -> list[Celestial]:
        # The natural bodies currently in the graph, in the order they were added.
        return list(self._celestials)

    def GetSatellites(self) -> list[Satellite]:
        # The artificial satellites currently in the graph.
        return list(self._satellites)

    def GetNodes(self) -> list:
        # Every node the graph will evaluate, natural and artificial alike.
        return list(self._celestials) + list(self._satellites)

    def GetLinks(self) -> list[tuple]:
        # Every unordered pair of nodes, the links the graph will evaluate.
        return list(combinations(self.GetNodes(), 2))

    def _OcculterCandidates(self, nodes: list) -> list:
        # Nodes, plus any central body that is not itself a node.
        bodies = list(nodes)
        seen = {b.naif_id for b in bodies}
        for sat in self._satellites:
            if sat.central.naif_id not in seen:
                bodies.append(sat.central)
                seen.add(sat.central.naif_id)
        return bodies

    def LinkKind(self, a: Celestial, b: Celestial) -> str:
        # "intra" if both endpoints share a time domain, else "inter".
        return "intra" if a.domain == b.domain else "inter"

    def GetLinkBudget(self) -> LinkBudget:
        # The link budget, mutable in place through its own setters.
        return self._link_budget

    def SetLinkBudget(self, budget: LinkBudget) -> ContactGraph:
        # Replace the link budget wholesale.
        if not isinstance(budget, LinkBudget):
            raise TypeError("SetLinkBudget expects a LinkBudget instance")
        self._link_budget = budget
        return self

    def GetGeometry(self) -> GeometryConfig:
        # The geometry configuration, mutable in place through its setters.
        return self._geometry

    def SetGeometry(self, config: GeometryConfig) -> ContactGraph:
        # Replace the geometry configuration wholesale.
        if not isinstance(config, GeometryConfig):
            raise TypeError("SetGeometry expects a GeometryConfig instance")
        self._geometry = config
        return self

    def GetKernelDir(self) -> Path:
        # Where SPICE kernels are cached.
        return self._kernel_dir

    def SetKernelDir(self, path: str | Path) -> ContactGraph:
        # Set the kernel cache directory.
        self._kernel_dir = Path(path)
        self._furnished = False
        return self

    def RequiredKernels(self) -> list[kern.Kernel]:
        # The kernels this set of bodies needs, without downloading anything.
        return kern.required_for(self._celestials, self._satellites)

    def FetchKernels(self, *, progress: bool = True) -> list[Path]:
        # Download whatever kernels are missing from the kernel directory.
        if not self._celestials and not self._satellites:
            raise ContactGraphError("add at least one body first")
        return kern.fetch(self.RequiredKernels(), self._kernel_dir, progress=progress)

    def LoadKernels(self) -> None:
        # Load the required kernels into SPICE and confirm they cover the bodies.
        if self._furnished:
            return
        required = self.RequiredKernels()
        kern.furnish(required, self._kernel_dir)
        needed = self._celestials + [s.central for s in self._satellites]
        kern.verify_coverage(needed, required, self._kernel_dir)
        self._furnished = True

    def GenerateContactGraph(
        self,
        *,
        days: float,
        start: str = DEFAULT_START_UTC,
        fetch: bool = True,
        progress: bool = True,
    ) -> ContactPlan:
        # Compute the contact plan over days days from start.
        nodes = self.GetNodes()
        if len(nodes) < 2:
            raise ContactGraphError(
                f"a contact graph needs at least two nodes; only {len(nodes)} added"
            )
        if days <= 0:
            raise ValueError(f"days must be positive, got {days!r}")

        if fetch:
            self.FetchKernels(progress=progress)
        self.LoadKernels()

        cfg = self._geometry
        t0 = sp.str2et(start)
        t1 = t0 + days * 86400.0

        if progress:
            print(
                f"span   {sp.et2utc(t0, 'ISOC', 0)} -> {sp.et2utc(t1, 'ISOC', 0)}"
                f"  ({days:.1f} d)"
            )

        ephemerides = SatelliteEphemerides(self._satellites)
        try:
            if self._satellites:
                ephemerides.Build(t0, t1)
                if progress:
                    for sat in self._satellites:
                        period = sat.elements.PeriodSeconds()
                        print(
                            f"propagated {sat.name} about {sat.central.name}, "
                            f"period {period / 60:.1f} min"
                        )

            return self._Generate(nodes, t0, t1, days, cfg, progress)
        finally:
            ephemerides.Cleanup()

    def _Generate(
        self,
        nodes: list,
        t0: float,
        t1: float,
        days: float,
        cfg: GeometryConfig,
        progress: bool,
    ) -> ContactPlan:
        if progress:
            print("prefiltering blocker candidates ...", flush=True)

        tic = time.time()
        links = self.GetLinks()
        candidates = geo.prefilter_occulters(
            self._OcculterCandidates(nodes), links, t0, t1, cfg
        )
        if progress:
            n_kept = sum(len(v) for v in candidates.values())
            n_possible = len(links) * max(len(nodes) - 2, 0)
            print(
                f"  {n_kept} plausible (link, blocker) pairs of {n_possible} "
                f"possible   [{time.time() - tic:.1f}s]"
            )

        contacts: list[Contact] = []
        summary: list[LinkSummary] = []

        for a, b in links:
            tic = time.time()
            cnfine = geo.window(t0, t1)

            blocked = sp.cell_double(20000)
            for c in candidates[(a.name, b.name)]:
                blocked = sp.wnunid(
                    blocked, geo.occultation_window(a, b, c, geo.window(t0, t1), cfg)
                )
            blocked = sp.wnunid(
                blocked, geo.corona_window(a, b, geo.window(t0, t1), cfg)
            )

            visible = sp.wndifd(cnfine, blocked)
            outages = geo.window_intervals(blocked)
            t_maxgap = max((e - s for s, e in outages), default=0.0)

            pieces: list[Contact] = []
            for s, e in geo.window_intervals(visible):
                if e - s < 1.0:
                    continue
                pieces.extend(self._subdivide(a, b, s, e))
            contacts.extend(pieces)

            summary.append(
                LinkSummary(
                    a=a.name,
                    b=b.name,
                    kind=self.LinkKind(a, b),
                    blockers=[c.name for c in candidates[(a.name, b.name)]],
                    n_contacts=len(pieces),
                    n_outages=len(outages),
                    contact_days=geo.window_total(visible) / 86400.0,
                    contact_fraction=geo.window_total(visible) / (t1 - t0),
                    t_maxgap_days=t_maxgap / 86400.0,
                    owlt_min_s=min((p.owlt_min_s for p in pieces), default=None),
                    owlt_max_s=max((p.owlt_max_s for p in pieces), default=None),
                )
            )

            if progress:
                blockers = ",".join(c.name for c in candidates[(a.name, b.name)]) or "-"
                print(
                    f"  {a.name:<9}{b.name:<9} {len(pieces):5d} contacts  "
                    f"gap {t_maxgap / 86400:7.2f} d  "
                    f"blockers={blockers:<20} [{time.time() - tic:5.1f}s]",
                    flush=True,
                )

        return ContactPlan(
            contacts=contacts,
            summary=summary,
            start_et=t0,
            stop_et=t1,
            meta={
                "span_days": days,
                "nodes": [b.name for b in nodes],
                "celestials": [b.name for b in self._celestials],
                "satellites": {
                    s.name: s.elements.AsDict() for s in self._satellites
                },
                "kernels": [k.filename for k in self.RequiredKernels()],
                "link_budget": self._link_budget.AsDict(),
                "geometry": cfg.AsDict(),
                "c_km_s": C_KM_S,
            },
        )

    def _subdivide(
        self, a: Celestial, b: Celestial, start: float, stop: float
    ) -> list[Contact]:
        # Cut one visibility interval into sub-contacts of near-constant rate.
        cfg = self._geometry
        budget = self._link_budget

        n = max(2, int(np.ceil((stop - start) / cfg.GetRateSample())) + 1)
        ets = np.linspace(start, stop, n)

        _, lt = sp.spkpos(b.name, ets, "J2000", "LT", a.name)
        lt = np.asarray(lt, dtype=float)
        rng = np.linalg.norm(
            np.asarray(sp.spkpos(b.name, ets, "J2000", "NONE", a.name)[0]), axis=1
        )
        rates = budget.RateBps(rng)
        tolerance = cfg.GetRateTolerance()
        floor = budget.GetMinRate()
        kind = self.LinkKind(a, b)

        pieces: list[Contact] = []
        seg_i = 0
        for i in range(1, n):
            drift = abs(rates[i] - rates[seg_i]) > tolerance * max(rates[seg_i], 1e-9)
            if drift or i == n - 1:
                lo, hi = seg_i, i
                rate = float(rates[lo : hi + 1].mean())
                if rate >= floor:
                    pieces.append(
                        Contact(
                            a=a.name,
                            b=b.name,
                            a_eid=a.eid,
                            b_eid=b.eid,
                            kind=kind,
                            start_et=float(ets[lo]),
                            stop_et=float(ets[hi]),
                            rate_bps=rate,
                            owlt_s=float(lt[lo : hi + 1].mean()),
                            owlt_min_s=float(lt[lo : hi + 1].min()),
                            owlt_max_s=float(lt[lo : hi + 1].max()),
                            range_min_km=float(rng[lo : hi + 1].min()),
                            range_max_km=float(rng[lo : hi + 1].max()),
                        )
                    )
                seg_i = i
        return pieces

    def __repr__(self) -> str:
        nodes = self.GetNodes()
        names = ", ".join(b.name for b in nodes)
        return f"ContactGraph({len(nodes)} nodes: {names})"
