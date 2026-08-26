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

    def AddSatellite(self, *args, **kwargs):
        # Add an artificial satellite from its orbital elements.
        raise NotImplementedError(
            "AddSatellite is not implemented yet; use AddCelestial for natural "
            "bodies in the meantime."
        )

    def GetCelestials(self) -> list[Celestial]:
        # The bodies currently in the graph, in the order they were added.
        return list(self._celestials)

    def GetLinks(self) -> list[tuple[Celestial, Celestial]]:
        # Every unordered pair of nodes, the links the graph will evaluate.
        return list(combinations(self._celestials, 2))

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
        return kern.required_for(self._celestials)

    def FetchKernels(self, *, progress: bool = True) -> list[Path]:
        # Download whatever kernels are missing from the kernel directory.
        if not self._celestials:
            raise ContactGraphError("add at least one celestial body first")
        return kern.fetch(self.RequiredKernels(), self._kernel_dir, progress=progress)

    def LoadKernels(self) -> None:
        # Load the required kernels into SPICE and confirm they cover the bodies.
        if self._furnished:
            return
        required = self.RequiredKernels()
        kern.furnish(required, self._kernel_dir)
        kern.verify_coverage(self._celestials, required, self._kernel_dir)
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
        if len(self._celestials) < 2:
            raise ContactGraphError(
                "a contact graph needs at least two nodes; "
                f"only {len(self._celestials)} added"
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
            print("prefiltering blocker candidates ...", flush=True)

        tic = time.time()
        links = self.GetLinks()
        candidates = geo.prefilter_occulters(self._celestials, links, t0, t1, cfg)
        if progress:
            n_kept = sum(len(v) for v in candidates.values())
            n_possible = len(links) * max(len(self._celestials) - 2, 0)
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
                "nodes": [b.name for b in self._celestials],
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
        names = ", ".join(b.name for b in self._celestials)
        return f"ContactGraph({len(self._celestials)} nodes: {names})"
