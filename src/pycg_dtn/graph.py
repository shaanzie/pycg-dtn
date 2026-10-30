"""The builder: add nodes, then generate the contact graph over them.
"""

from __future__ import annotations

import math
import time
from itertools import combinations
from pathlib import Path

import numpy as np
import spiceypy as sp

from . import bundletrace, visualize
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
from .stations import GroundStation, station_id

DEFAULT_START_UTC = "2026-01-01T00:00:00"


class ContactGraphError(RuntimeError):
    """Raised when the graph is not in a state that can be generated from."""


def _is_station(node) -> bool:
    return getattr(node, "is_station", False)


class ContactGraph:
    """A scenario under construction: its nodes, its radios, its geometry."""
    def __init__(
        self,
        *,
        kernel_dir: str | Path | None = None,
        link_budget: LinkBudget | None = None,
        geometry: GeometryConfig | None = None,
    ) -> None:
        self._celestials: list[Celestial] = []
        self._satellites: list = []
        self._stations: list[GroundStation] = []
        self._kernel_dir = Path(kernel_dir) if kernel_dir else Path.cwd() / "kernels"
        self._link_budget = link_budget or LinkBudget()
        self._budgets: dict[tuple[str, str], LinkBudget] = {}
        self._groups: dict[str, str] = {}
        self._disabled: set[frozenset] = set()
        self._geometry = geometry or GeometryConfig()
        self._furnished = False
        self._plan: ContactPlan | None = None

    def AddCelestial(
        self, name: str, *, eid: str | None = None, group: str | None = None
    ) -> Celestial:
        """Add a natural body, a planet, a moon, or the Sun as a node."""
        body = resolve(name, eid=eid)

        for existing in self._celestials:
            if existing.naif_id == body.naif_id:
                raise UnknownCelestialBodyError(
                    f"{name!r} is already in the graph as {existing.name} "
                    f"(NAIF {existing.naif_id})"
                )

        self._celestials.append(body)
        if group:
            self._groups[body.name] = group
        return body

    def _CheckNameFree(self, name: str) -> None:
        for existing in self._satellites + self._stations:
            if existing.name.upper() == name.upper():
                raise SatelliteError(f"{name!r} is already in the graph")

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
        group: str | None = None,
    ) -> Satellite:
        """Add an artificial satellite orbiting central."""
        if (semi_major_axis_km is None) == (altitude_km is None):
            raise SatelliteError(
                f"{name}: give exactly one of semi_major_axis_km or altitude_km"
            )

        self._CheckNameFree(name)
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
        if group:
            self._groups[sat.name] = group
        self._furnished = False
        return sat

    def AddSatelliteFromState(
        self,
        name: str,
        central: str,
        state_km: list[float],
        epoch_utc: str,
        *,
        frame: str = "J2000",
        eid: str | None = None,
        group: str | None = None,
    ) -> Satellite:
        """Add a satellite from a Cartesian state about central.

        ``state_km`` is [x, y, z, vx, vy, vz] in km and km/s, in ``frame``, at
        ``epoch_utc``. It is converted to osculating two-body elements.
        """
        if len(state_km) != 6:
            raise SatelliteError(f"{name}: state_km needs 6 values, got {len(state_km)}")

        body = resolve(central)
        self._LoadSmallKernels(with_gm=True)
        et = sp.str2et(epoch_utc)
        state = np.asarray(state_km, dtype=float)
        if frame.upper() != "J2000":
            state = np.asarray(sp.sxform(frame, "J2000", et), dtype=float).dot(state)

        mu = float(sp.bodvrd(body.name, "GM", 1)[1][0])
        elts = sp.oscltx(state, et, mu)
        eccentricity = float(elts[1])
        if eccentricity >= 1.0:
            raise SatelliteError(
                f"{name}: the state is not a closed orbit about {body.name} "
                f"(eccentricity {eccentricity:.4f})"
            )

        return self.AddSatellite(
            name,
            central,
            semi_major_axis_km=float(elts[9]),
            eccentricity=eccentricity,
            inclination_deg=math.degrees(elts[2]),
            raan_deg=math.degrees(elts[3]),
            arg_periapsis_deg=math.degrees(elts[4]),
            mean_anomaly_deg=math.degrees(elts[5]),
            epoch_utc=epoch_utc,
            eid=eid,
            group=group,
        )

    def AddGroundStation(
        self,
        name: str,
        central: str,
        *,
        latitude_deg: float,
        longitude_deg: float,
        altitude_km: float = 0.0,
        min_elevation_deg: float = 0.0,
        eid: str | None = None,
        group: str | None = None,
    ) -> GroundStation:
        """Add a fixed site on the surface of central.

        Latitude is geodetic, longitude east-positive, both in the body's IAU
        frame. The station only sees targets above ``min_elevation_deg``.
        Two stations on the same body are never linked.
        """
        self._CheckNameFree(name)
        body = resolve(central)
        station = GroundStation(
            name=name.upper(),
            naif_id=station_id(len(self._stations)),
            central=body,
            latitude_deg=latitude_deg,
            longitude_deg=longitude_deg,
            altitude_km=altitude_km,
            min_elevation_deg=min_elevation_deg,
            eid=eid or "",
        )
        self._stations.append(station)
        if group:
            self._groups[station.name] = group
        self._furnished = False
        return station

    def _LoadSmallKernels(self, *, with_gm: bool = False) -> None:
        small = [kern.LSK, kern.PCK]
        if with_gm:
            small.append(kern.GM)
        kern.fetch(small, self._kernel_dir, progress=False)
        kern.furnish(small, self._kernel_dir)

    def _EquatorialRadius(self, body: Celestial) -> float:
        try:
            return float(max(sp.bodvrd(body.name, "RADII", 3)[1]))
        except Exception:
            self._LoadSmallKernels()
            return float(max(sp.bodvrd(body.name, "RADII", 3)[1]))

    def GetCelestials(self) -> list[Celestial]:
        """The natural bodies currently in the graph, in the order they were added."""
        return list(self._celestials)

    def GetSatellites(self) -> list[Satellite]:
        """The artificial satellites currently in the graph."""
        return list(self._satellites)

    def GetStations(self) -> list[GroundStation]:
        """The ground stations currently in the graph."""
        return list(self._stations)

    def GetNodes(self) -> list:
        """Every node the graph will evaluate, natural and artificial alike."""
        return list(self._celestials) + list(self._satellites) + list(self._stations)

    def _FindNode(self, name: str):
        for node in self.GetNodes():
            if node.name == name.upper():
                return node
        raise ContactGraphError(f"no node named {name!r} in the graph")

    def GetNodeGroup(self, name: str) -> str:
        """The group a node belongs to; a node with no group is its own group."""
        node = self._FindNode(name)
        return self._groups.get(node.name, node.name)

    def SetNodeGroup(self, name: str, group: str) -> ContactGraph:
        """Put a node in a group, for per-group radios and disabled links."""
        node = self._FindNode(name)
        if not group:
            raise ContactGraphError("group must be a non-empty string")
        self._groups[node.name] = group
        return self

    def DisableLinks(self, group_a: str, group_b: str) -> ContactGraph:
        """Never link a node of group_a with a node of group_b (either way)."""
        self._disabled.add(frozenset((group_a, group_b)))
        return self

    def EnableLinks(self, group_a: str, group_b: str) -> ContactGraph:
        """Undo DisableLinks for this pair of groups."""
        self._disabled.discard(frozenset((group_a, group_b)))
        return self

    def GetDisabledLinks(self) -> list[tuple[str, str]]:
        """The group pairs that are never linked."""
        pairs = []
        for pair in self._disabled:
            names = sorted(pair)
            if len(names) == 1:
                names = [names[0], names[0]]
            pairs.append((names[0], names[1]))
        return sorted(pairs)

    def _IsLinkable(self, a, b) -> bool:
        # Ground networks are outside the model
        if _is_station(a) and _is_station(b):
            if a.central.naif_id == b.central.naif_id:
                return False
        group_a = self._groups.get(a.name, a.name)
        group_b = self._groups.get(b.name, b.name)
        return frozenset((group_a, group_b)) not in self._disabled

    def GetLinks(self) -> list[tuple]:
        """Every unordered pair of nodes the graph will evaluate."""
        links = []
        for a, b in combinations(self.GetNodes(), 2):
            if self._IsLinkable(a, b):
                links.append((a, b))
        return links

    def _OcculterCandidates(self, nodes: list) -> list:
        """Nodes, plus any central body that is not itself a node."""
        bodies = list(nodes)
        seen = {b.naif_id for b in bodies}
        for sat in self._satellites + self._stations:
            if sat.central.naif_id not in seen:
                bodies.append(sat.central)
                seen.add(sat.central.naif_id)
        return bodies

    def LinkKind(self, a: Celestial, b: Celestial) -> str:
        """"intra" if both endpoints share a time domain, else "inter"."""
        return "intra" if a.domain == b.domain else "inter"

    def GetLinkBudget(self) -> LinkBudget:
        """The default link budget, mutable in place through its own setters."""
        return self._link_budget

    def SetLinkBudget(self, budget: LinkBudget) -> ContactGraph:
        """Replace the default link budget wholesale."""
        if not isinstance(budget, LinkBudget):
            raise TypeError("SetLinkBudget expects a LinkBudget instance")
        self._link_budget = budget
        return self

    def SetLinkBudgetFor(
        self, tx_group: str, rx_group: str, budget: LinkBudget
    ) -> ContactGraph:
        """Use ``budget`` for transmissions from tx_group to rx_group.

        If the reverse direction has no budget of its own, it uses this one too.
        """
        if not isinstance(budget, LinkBudget):
            raise TypeError("SetLinkBudgetFor expects a LinkBudget instance")
        self._budgets[(tx_group, rx_group)] = budget
        return self

    def GetLinkBudgetFor(self, tx_group: str, rx_group: str) -> LinkBudget:
        """The budget used from tx_group to rx_group: its own, else the reverse
        direction's, else the default."""
        if (tx_group, rx_group) in self._budgets:
            return self._budgets[(tx_group, rx_group)]
        if (rx_group, tx_group) in self._budgets:
            return self._budgets[(rx_group, tx_group)]
        return self._link_budget

    def _BudgetBetween(self, tx, rx) -> LinkBudget:
        tx_group = self._groups.get(tx.name, tx.name)
        rx_group = self._groups.get(rx.name, rx.name)
        return self.GetLinkBudgetFor(tx_group, rx_group)

    def GetGeometry(self) -> GeometryConfig:
        """The geometry configuration, mutable in place through its setters."""
        return self._geometry

    def SetGeometry(self, config: GeometryConfig) -> ContactGraph:
        """Replace the geometry configuration wholesale."""
        if not isinstance(config, GeometryConfig):
            raise TypeError("SetGeometry expects a GeometryConfig instance")
        self._geometry = config
        return self

    def GetKernelDir(self) -> Path:
        """Where SPICE kernels are cached."""
        return self._kernel_dir

    def SetKernelDir(self, path: str | Path) -> ContactGraph:
        """Set the kernel cache directory."""
        self._kernel_dir = Path(path)
        self._furnished = False
        return self

    def RequiredKernels(self) -> list[kern.Kernel]:
        """The kernels this set of bodies needs, without downloading anything."""
        return kern.required_for(self._celestials, self._satellites, self._stations)

    def FetchKernels(self, *, progress: bool = True) -> list[Path]:
        """Download whatever kernels are missing from the kernel directory."""
        if not self.GetNodes():
            raise ContactGraphError("add at least one body first")
        return kern.fetch(self.RequiredKernels(), self._kernel_dir, progress=progress)

    def LoadKernels(self) -> None:
        """Load the required kernels into SPICE and confirm they cover the bodies."""
        if self._furnished:
            return
        required = self.RequiredKernels()
        kern.furnish(required, self._kernel_dir)
        needed = list(self._celestials)
        for node in self._satellites + self._stations:
            needed.append(node.central)
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
        """Compute the contact plan over days days from start."""
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

        ephemerides = SatelliteEphemerides(self._satellites, self._stations)
        try:
            if self._satellites or self._stations:
                ephemerides.Build(t0, t1)
                if progress:
                    for sat in self._satellites:
                        period = sat.elements.PeriodSeconds()
                        print(
                            f"propagated {sat.name} about {sat.central.name}, "
                            f"period {period / 60:.1f} min"
                        )
                    for station in self._stations:
                        print(
                            f"placed {station.name} on {station.central.name} at "
                            f"{station.latitude_deg:.3f}, {station.longitude_deg:.3f} "
                            f"(mask {station.min_elevation_deg:g} deg)"
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

            # A station's own body is handled by its elevation mask instead
            hosts = set()
            for node in (a, b):
                if _is_station(node):
                    hosts.add(node.central.naif_id)
            blockers = []
            for c in candidates[(a.name, b.name)]:
                if c.naif_id not in hosts:
                    blockers.append(c)

            blocked = sp.cell_double(20000)
            for c in blockers:
                blocked = sp.wnunid(
                    blocked, geo.occultation_window(a, b, c, geo.window(t0, t1), cfg)
                )
            blocked = sp.wnunid(
                blocked, geo.corona_window(a, b, geo.window(t0, t1), cfg)
            )
            for station, target in ((a, b), (b, a)):
                if _is_station(station):
                    above = geo.elevation_window(station, target, geo.window(t0, t1), cfg)
                    blocked = sp.wnunid(blocked, sp.wndifd(geo.window(t0, t1), above))

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
                    blockers=[c.name for c in blockers],
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
                names = ",".join(c.name for c in blockers) or "-"
                print(
                    f"  {a.name:<9}{b.name:<9} {len(pieces):5d} contacts  "
                    f"gap {t_maxgap / 86400:7.2f} d  "
                    f"blockers={names:<20} [{time.time() - tic:5.1f}s]",
                    flush=True,
                )

        link_budgets = {}
        for (tx, rx), budget in self._budgets.items():
            link_budgets[f"{tx}->{rx}"] = budget.AsDict()

        self._plan = ContactPlan(
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
                "stations": {s.name: s.AsDict() for s in self._stations},
                "groups": dict(self._groups),
                "kernels": [k.filename for k in self.RequiredKernels()],
                "link_budget": self._link_budget.AsDict(),
                "link_budgets": link_budgets,
                "disabled_links": self.GetDisabledLinks(),
                "geometry": cfg.AsDict(),
                "c_km_s": C_KM_S,
            },
        )
        return self._plan

    def GenerateVisualizer(
        self,
        step_size: float,
        *,
        out: str | Path = "out/visualizer.html",
        trace: str | Path | None = None,
        title: str | None = None,
        days: float | None = None,
        start: str = DEFAULT_START_UTC,
    ) -> Path:
        """Write a self-contained HTML view of the graph.
        """
        plan = self._plan
        if plan is None:
            if days is None:
                raise ContactGraphError(
                    "no contact plan yet; call GenerateContactGraph() first, "
                    "or pass days= to generate one here"
                )
            plan = self.GenerateContactGraph(days=days, start=start)

        # Orbit periods come from GM, which a satellite-free graph does not load
        kern.fetch([kern.GM], self._kernel_dir, progress=False)
        kern.furnish([kern.GM], self._kernel_dir)

        loaded = bundletrace.load(trace) if trace is not None else None

        # Satellite ephemerides are scratch data discarded once a plan is built,
        # so they have to be rebuilt
        ephemerides = SatelliteEphemerides(self._satellites, self._stations)
        try:
            if self._satellites or self._stations:
                # The page draws one full revolution per satellite, which for a
                # period longer than the plan runs off the end of it
                longest = 0.0
                for s in self._satellites:
                    longest = max(longest, s.elements.PeriodSeconds())
                ephemerides.Build(
                    plan.start_et, max(plan.stop_et, plan.start_et + longest)
                )
            payload = visualize.build_payload(
                self,
                plan,
                float(step_size),
                trace=loaded,
                title=title or f"PyCG-DTN — {len(self.GetNodes())} nodes",
            )
        finally:
            ephemerides.Cleanup()

        return visualize.write(payload, out)

    def _subdivide(
        self, a: Celestial, b: Celestial, start: float, stop: float
    ) -> list[Contact]:
        """Cut one visibility interval into sub-contacts of near-constant rate.

        Each direction uses its own budget; a piece is kept only if both
        directions clear their rate floor.
        """
        cfg = self._geometry
        budget_ab = self._BudgetBetween(a, b)
        budget_ba = self._BudgetBetween(b, a)

        n = max(2, int(np.ceil((stop - start) / cfg.GetRateSample())) + 1)
        ets = np.linspace(start, stop, n)

        _, lt = sp.spkpos(b.name, ets, "J2000", "LT", a.name)
        lt = np.asarray(lt, dtype=float)
        rng = np.linalg.norm(
            np.asarray(sp.spkpos(b.name, ets, "J2000", "NONE", a.name)[0]), axis=1
        )
        rates_ab = budget_ab.RateBps(rng)
        rates_ba = budget_ba.RateBps(rng)
        tolerance = cfg.GetRateTolerance()
        kind = self.LinkKind(a, b)

        pieces: list[Contact] = []
        seg_i = 0
        for i in range(1, n):
            drift_ab = abs(rates_ab[i] - rates_ab[seg_i]) > tolerance * max(
                rates_ab[seg_i], 1e-9
            )
            drift_ba = abs(rates_ba[i] - rates_ba[seg_i]) > tolerance * max(
                rates_ba[seg_i], 1e-9
            )
            if drift_ab or drift_ba or i == n - 1:
                lo, hi = seg_i, i
                rate_ab = float(rates_ab[lo : hi + 1].mean())
                rate_ba = float(rates_ba[lo : hi + 1].mean())
                ab_ok = rate_ab >= budget_ab.GetMinRate()
                ba_ok = rate_ba >= budget_ba.GetMinRate()
                if ab_ok and ba_ok:
                    pieces.append(
                        Contact(
                            a=a.name,
                            b=b.name,
                            a_eid=a.eid,
                            b_eid=b.eid,
                            kind=kind,
                            start_et=float(ets[lo]),
                            stop_et=float(ets[hi]),
                            rate_bps=rate_ab,
                            owlt_s=float(lt[lo : hi + 1].mean()),
                            owlt_min_s=float(lt[lo : hi + 1].min()),
                            owlt_max_s=float(lt[lo : hi + 1].max()),
                            range_min_km=float(rng[lo : hi + 1].min()),
                            range_max_km=float(rng[lo : hi + 1].max()),
                            rate_ba_bps=rate_ba,
                        )
                    )
                seg_i = i
        return pieces

    def __repr__(self) -> str:
        nodes = self.GetNodes()
        names = ", ".join(b.name for b in nodes)
        return f"ContactGraph({len(nodes)} nodes: {names})"
