"""
Command-line front end
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .celestials import UnknownCelestialBodyError
from .geometry import GeometryConfig
from .graph import DEFAULT_START_UTC, ContactGraph, ContactGraphError
from .kernels import KernelError
from .linkbudget import LinkBudget
from .satellites import SatelliteError

_SAT_KEYS = {
    "alt": "altitude_km",
    "altitude_km": "altitude_km",
    "sma": "semi_major_axis_km",
    "semi_major_axis_km": "semi_major_axis_km",
    "ecc": "eccentricity",
    "eccentricity": "eccentricity",
    "inc": "inclination_deg",
    "inclination_deg": "inclination_deg",
    "raan": "raan_deg",
    "raan_deg": "raan_deg",
    "argp": "arg_periapsis_deg",
    "arg_periapsis_deg": "arg_periapsis_deg",
    "ma": "mean_anomaly_deg",
    "mean_anomaly_deg": "mean_anomaly_deg",
    "eid": "eid",
}


def _parse_satellite(spec: str) -> tuple[str, str, dict]:
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    if len(parts) < 3:
        raise SatelliteError(
            f"satellite {spec!r} must be NAME,CENTRAL,key=value,... "
            "for example: RELAY,Mars,alt=400,inc=93"
        )

    name, central = parts[0], parts[1]
    kwargs: dict = {}
    for item in parts[2:]:
        if "=" not in item:
            raise SatelliteError(f"satellite {name}: expected key=value, got {item!r}")
        key, _, value = item.partition("=")
        key = key.strip().lower()
        if key not in _SAT_KEYS:
            raise SatelliteError(
                f"satellite {name}: unknown option {key!r}; "
                f"choose from {', '.join(sorted(set(_SAT_KEYS)))}"
            )
        canonical = _SAT_KEYS[key]
        if canonical == "eid":
            kwargs[canonical] = value.strip()
        else:
            try:
                kwargs[canonical] = float(value)
            except ValueError as exc:
                raise SatelliteError(
                    f"satellite {name}: {key} must be a number, got {value!r}"
                ) from exc

    return name, central, kwargs


def _build_graph(args: argparse.Namespace) -> ContactGraph:
    budget = LinkBudget()
    for attr, setter in (
        ("tx_power", budget.SetTxPower),
        ("frequency", budget.SetFrequency),
        ("bandwidth", budget.SetBandwidth),
        ("tx_gain", budget.SetTxGain),
        ("rx_gain", budget.SetRxGain),
        ("min_rate", budget.SetMinRate),
    ):
        value = getattr(args, attr, None)
        if value is not None:
            setter(value)

    geometry = GeometryConfig()
    if getattr(args, "sep_exclusion", None) is not None:
        geometry.SetSepExclusion(args.sep_exclusion)

    cg = ContactGraph(
        kernel_dir=args.kernel_dir, link_budget=budget, geometry=geometry
    )
    for name in args.bodies or []:
        cg.AddCelestial(name)
    for spec in getattr(args, "satellite", None) or []:
        name, central, kwargs = _parse_satellite(spec)
        cg.AddSatellite(name, central, **kwargs)

    if not cg.GetNodes():
        raise ContactGraphError("give at least one --bodies or --satellite")
    return cg


def _cmd_kernels(args: argparse.Namespace) -> int:
    cg = _build_graph(args)
    required = cg.RequiredKernels()
    total = sum(k.approx_mb for k in required)
    print(f"kernel directory: {cg.GetKernelDir()}")
    print(f"{len(required)} kernels, about {total:,.0f} MB total\n")
    for k in required:
        present = (cg.GetKernelDir() / k.filename).is_file()
        mark = "have" if present else "need"
        print(f"  [{mark}] {k.filename:<16} {k.approx_mb:8,.1f} MB   {k.purpose}")
    return 0


def _cmd_fetch(args: argparse.Namespace) -> int:
    cg = _build_graph(args)
    cg.FetchKernels()
    print("\nAll kernels present.")
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    cg = _build_graph(args)
    plan = cg.GenerateContactGraph(
        days=args.days, start=args.start, fetch=not args.no_fetch
    )
    written = plan.Write(args.out)

    print(f"\n{len(plan)} contacts over {args.days:g} days")
    for path in written.values():
        print(f"  wrote {path}")

    print("\nlongest outage per link:")
    for s in plan.LongestOutages(12):
        print(
            f"  {s.a:<9}{s.b:<9}{s.kind:<6}{s.t_maxgap_days:8.2f} d   "
            f"contact {100 * s.contact_fraction:5.1f}%"
        )
    return 0


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--bodies",
        nargs="+",
        default=[],
        metavar="NAME",
        help="celestial bodies to use as nodes, e.g. Earth Mars Phobos",
    )
    p.add_argument(
        "--satellite",
        action="append",
        default=[],
        metavar="SPEC",
        help="artificial satellite as NAME,CENTRAL,key=value,...",
    )
    p.add_argument(
        "--kernel-dir",
        type=Path,
        default=Path.cwd() / "kernels",
        help="where to cache SPICE kernels (default: ./kernels)",
    )


def _add_radio(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("link budget")
    g.add_argument("--tx-power", type=float, help="transmit power, W (default 100)")
    g.add_argument("--frequency", type=float, help="carrier, Hz (default 8.42e9)")
    g.add_argument("--bandwidth", type=float, help="bandwidth, Hz (default 1e6)")
    g.add_argument("--tx-gain", type=float, help="transmit gain, dBi (default 48)")
    g.add_argument("--rx-gain", type=float, help="receive gain, dBi (default 74.18)")
    g.add_argument("--min-rate", type=float, help="rate floor, bits/s (default 1)")
    g.add_argument(
        "--sep-exclusion",
        type=float,
        help="solar exclusion angle, degrees (default 3)",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pycg",
        description="Build DTN contact graphs for deep-space networks from SPICE.",
    )
    parser.add_argument("--version", action="version", version=f"pycg-dtn {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_kernels = sub.add_parser(
        "kernels", help="show which SPICE kernels a body set needs"
    )
    _add_common(p_kernels)
    p_kernels.set_defaults(func=_cmd_kernels)

    p_fetch = sub.add_parser("fetch", help="download the required SPICE kernels")
    _add_common(p_fetch)
    p_fetch.set_defaults(func=_cmd_fetch)

    p_build = sub.add_parser("build", help="generate a contact graph")
    _add_common(p_build)
    _add_radio(p_build)
    p_build.add_argument(
        "--days", type=float, required=True, help="length of the span to analyse"
    )
    p_build.add_argument(
        "--start",
        default=DEFAULT_START_UTC,
        help=f"start epoch, UTC (default {DEFAULT_START_UTC})",
    )
    p_build.add_argument(
        "--out", type=Path, default=Path("out"), help="output directory (default out/)"
    )
    p_build.add_argument(
        "--no-fetch",
        action="store_true",
        help="fail rather than download missing kernels",
    )
    p_build.set_defaults(func=_cmd_build)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (
        UnknownCelestialBodyError,
        KernelError,
        ContactGraphError,
        SatelliteError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  
    raise SystemExit(main())
