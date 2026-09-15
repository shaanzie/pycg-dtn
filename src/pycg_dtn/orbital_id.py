"""
Orbital IPs: default endpoint identifiers built from where a node is, not
just its name.

The scheme name is ``oip`` (orbital IP), a peer to BPv7's own ``dtn``/``ipn``
schemes (RFC 9171 SS4.2.5.1). It carries two version fields up front -- which
Bundle Protocol version the endpoint is reachable over, and which version of
this addressing scheme produced the rest of the string -- so either can move
independently later without breaking existing addresses:

``oip://<bp-version>::<scheme-version>::<domain>::<regime>::<node-id>``

optionally followed by an orbital-state suffix for a satellite. ``domain``
and ``regime`` are a truncatable scope -- everything in Mars's clock domain
shares ``oip://bp7::v1::mars``, everything orbiting something there shares
``oip://bp7::v1::mars::sat`` -- while the state suffix (epoch and Keplerian
elements) is opaque payload appended after the scope, never something a
query truncates over.

``node_id`` is a routing label, not a display name -- a node's human-facing
``name`` is untouched and keeps showing up wherever it always has (the
visualizer's focus list, click-to-select, etc). This module only ever
produces the value that lands in ``eid``.
"""

from __future__ import annotations

SCHEME = "oip"
BP_VERSION = "bp7"
SCHEME_VERSION = "v1"

REGIME_BODY = "body"
REGIME_SATELLITE = "sat"


def _slug(name: str) -> str:
    return name.strip().lower().replace(" ", "-").replace("_", "-")


def _fmt(value: float, places: int) -> str:
    return f"{float(value):.{places}f}"


def BuildEid(
    domain: str,
    regime: str,
    node_id: str,
    *,
    elements: dict[str, float | str] | None = None,
) -> str:
    """The default orbital-IP EID for one node.

    ``elements``, when given, is a :meth:`KeplerianElements.AsDict` result
    and is appended as an orbital-state suffix -- present for a satellite,
    absent for a natural body.
    """
    prefix = (
        f"{SCHEME}://{BP_VERSION}::{SCHEME_VERSION}::"
        f"{_slug(domain)}::{regime}::{_slug(node_id)}"
    )
    if elements is None:
        return prefix
    state = "::".join(
        [
            str(elements["epoch_utc"]),
            _fmt(elements["semi_major_axis_km"], 3),
            _fmt(elements["eccentricity"], 6),
            _fmt(elements["inclination_deg"], 6),
            _fmt(elements["raan_deg"], 6),
            _fmt(elements["arg_periapsis_deg"], 6),
            _fmt(elements["mean_anomaly_deg"], 6),
        ]
    )
    return f"{prefix}::{state}"
