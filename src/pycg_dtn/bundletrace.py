"""
Bundle traces: where a bundle actually went, hop by hop.

A bundle trace is the record of a routing run over a contact plan, produced by
ION, ns-3 or your own router. PyCG-DTN reads it back and draws a timeline; it
does not route.

Only ``id`` and ``hops`` are required per bundle, and only ``to`` and
``tx_start_utc`` per hop. The full schema is documented at
https://pycg-dtn.readthedocs.io/en/latest/bundletrace.html
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

HOP_STATUS = ("forwarded", "delivered", "dropped", "queued", "expired")


class BundleTraceError(ValueError):
    """Raised when a bundle trace is malformed."""


@dataclass
class Hop:
    """One forwarding step: a bundle leaving one node and arriving at another."""

    to: str
    tx_start_utc: str
    sender: str = ""
    tx_stop_utc: str = ""
    rx_utc: str = ""
    owlt_s: float | None = None
    status: str = "forwarded"

    @property
    def is_terminal(self) -> bool:
        return self.status in ("delivered", "dropped", "expired")


@dataclass
class Bundle:
    """One bundle and the path it took."""

    id: str
    hops: list[Hop] = field(default_factory=list)
    source: str = ""
    destination: str = ""
    created_utc: str = ""
    size_bytes: int | None = None
    delivered: bool | None = None

    def __post_init__(self) -> None:
        if not self.source and self.hops:
            self.source = self.hops[0].sender
        if not self.destination and self.hops:
            self.destination = self.hops[-1].to
        if self.delivered is None:
            self.delivered = any(h.status == "delivered" for h in self.hops)

    @property
    def n_hops(self) -> int:
        return len(self.hops)

    def Nodes(self) -> list[str]:
        """Every node the bundle touched, in the order it reached them."""
        seen: list[str] = []
        for hop in self.hops:
            for node in (hop.sender, hop.to):
                if node and node not in seen:
                    seen.append(node)
        return seen


@dataclass
class BundleTrace:
    """A run's worth of bundles."""

    bundles: list[Bundle] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.bundles)

    def __iter__(self):
        return iter(self.bundles)

    def Get(self, bundle_id: str) -> Bundle:
        for b in self.bundles:
            if b.id == bundle_id:
                return b
        raise BundleTraceError(f"no bundle {bundle_id!r} in this trace")

    def AsDict(self) -> dict:
        return {
            "meta": self.meta,
            "bundles": [
                {
                    "id": b.id,
                    "source": b.source,
                    "destination": b.destination,
                    "created_utc": b.created_utc,
                    "size_bytes": b.size_bytes,
                    "delivered": b.delivered,
                    "hops": [
                        {
                            "from": h.sender,
                            "to": h.to,
                            "tx_start_utc": h.tx_start_utc,
                            "tx_stop_utc": h.tx_stop_utc,
                            "rx_utc": h.rx_utc,
                            "owlt_s": h.owlt_s,
                            "status": h.status,
                        }
                        for h in b.hops
                    ],
                }
                for b in self.bundles
            ],
        }


def _hop_from_dict(raw: dict, bundle_id: str, index: int) -> Hop:
    where = f"bundle {bundle_id!r} hop {index}"
    if not isinstance(raw, dict):
        raise BundleTraceError(f"{where}: expected an object, got {type(raw).__name__}")

    to = raw.get("to") or ""
    if not to:
        raise BundleTraceError(f"{where}: missing required field 'to'")
    tx_start = raw.get("tx_start_utc") or ""
    if not tx_start:
        raise BundleTraceError(f"{where}: missing required field 'tx_start_utc'")

    owlt = raw.get("owlt_s")
    if owlt is not None:
        try:
            owlt = float(owlt)
        except (TypeError, ValueError) as exc:
            raise BundleTraceError(f"{where}: owlt_s must be a number") from exc

    return Hop(
        to=str(to),
        tx_start_utc=str(tx_start),
        sender=str(raw.get("from") or ""),
        tx_stop_utc=str(raw.get("tx_stop_utc") or ""),
        rx_utc=str(raw.get("rx_utc") or ""),
        owlt_s=owlt,
        status=str(raw.get("status") or "forwarded"),
    )


def _bundle_from_dict(raw: dict, index: int) -> Bundle:
    if not isinstance(raw, dict):
        raise BundleTraceError(f"bundle {index}: expected an object")

    bundle_id = str(raw.get("id") or "").strip()
    if not bundle_id:
        raise BundleTraceError(f"bundle {index}: missing required field 'id'")

    raw_hops = raw.get("hops")
    if not isinstance(raw_hops, list):
        raise BundleTraceError(f"bundle {bundle_id!r}: 'hops' must be a list")

    size = raw.get("size_bytes")
    if size is not None:
        try:
            size = int(size)
        except (TypeError, ValueError) as exc:
            raise BundleTraceError(
                f"bundle {bundle_id!r}: size_bytes must be an integer"
            ) from exc

    return Bundle(
        id=bundle_id,
        hops=[_hop_from_dict(h, bundle_id, i) for i, h in enumerate(raw_hops)],
        source=str(raw.get("source") or ""),
        destination=str(raw.get("destination") or ""),
        created_utc=str(raw.get("created_utc") or ""),
        size_bytes=size,
        delivered=raw.get("delivered"),
    )


def loads(text: str) -> BundleTrace:
    """Parse a bundle trace from JSON text."""
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BundleTraceError(f"not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise BundleTraceError("a bundle trace must be a JSON object")

    bundles = raw.get("bundles")
    if not isinstance(bundles, list):
        raise BundleTraceError(
            "a bundle trace needs a 'bundles' list; see the schema in "
            "pycg_dtn.bundletrace"
        )

    return BundleTrace(
        bundles=[_bundle_from_dict(b, i) for i, b in enumerate(bundles)],
        meta=raw.get("meta") if isinstance(raw.get("meta"), dict) else {},
    )


def load(path: str | Path) -> BundleTrace:
    """Read and validate a ``bundle-trace.json``."""
    path = Path(path)
    if not path.is_file():
        raise BundleTraceError(f"no bundle trace at {path}")
    return loads(path.read_text())
