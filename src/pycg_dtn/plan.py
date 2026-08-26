"""The generated contact plan, and the formats it can be written out in.
The ION CSV format is the contact plan ingested by NASA JPL's Interplanetary
Overlay Network, the reference DTN implementation:
https://github.com/nasa-jpl/ION-DTN
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import spiceypy as sp


@dataclass
class Contact:
    """One interval of usable connectivity between two nodes."""

    a: str
    b: str
    a_eid: str
    b_eid: str
    kind: str  
    start_et: float
    stop_et: float
    rate_bps: float
    owlt_s: float
    owlt_min_s: float
    owlt_max_s: float
    range_min_km: float
    range_max_km: float

    @property
    def duration_s(self) -> float:
        return self.stop_et - self.start_et

    @property
    def volume_bits(self) -> float:
        """How much data this contact can carry end to end."""
        return self.rate_bps * self.duration_s


@dataclass
class LinkSummary:
    """Per-link statistics, most usefully the longest outage."""

    a: str
    b: str
    kind: str
    blockers: list[str]
    n_contacts: int
    n_outages: int
    contact_days: float
    contact_fraction: float
    t_maxgap_days: float
    owlt_min_s: float | None
    owlt_max_s: float | None


@dataclass
class ContactPlan:
    """Everything ``GenerateContactGraph`` produced."""

    contacts: list[Contact]
    summary: list[LinkSummary]
    start_et: float
    stop_et: float
    meta: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.contacts)

    def __iter__(self):
        return iter(self.contacts)

    @property
    def start_utc(self) -> str:
        return sp.et2utc(self.start_et, "ISOC", 3)

    @property
    def stop_utc(self) -> str:
        return sp.et2utc(self.stop_et, "ISOC", 3)

    def ForLink(self, a: str, b: str) -> list[Contact]:
        """Every contact on one link, in either direction, time-ordered."""
        want = {a.upper(), b.upper()}
        return sorted(
            (c for c in self.contacts if {c.a, c.b} == want),
            key=lambda c: c.start_et,
        )

    def LongestOutages(self, n: int = 10) -> list[LinkSummary]:
        """The links with the worst maximum gap, worst first."""
        return sorted(self.summary, key=lambda s: -s.t_maxgap_days)[:n]


    def ToIonCsv(self, path: str | Path) -> Path:
        """Write an ION contact plan."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as fh:
            for c in sorted(self.contacts, key=lambda x: x.start_et):
                s = int(round(c.start_et - self.start_et))
                e = int(round(c.stop_et - self.start_et))
                if e <= s:
                    continue
                for src, dst in ((c.a_eid, c.b_eid), (c.b_eid, c.a_eid)):
                    fh.write(f"a contact +{s} +{e} {src} {dst} {int(c.rate_bps)}\n")
                    fh.write(f"a range +{s} +{e} {src} {dst} {c.owlt_s:.6f}\n")
        return path

    def ToJson(self, path: str | Path) -> Path:
        """Write the full plan, metadata included, as JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "meta": {
                "start_utc": self.start_utc,
                "stop_utc": self.stop_utc,
                **self.meta,
            },
            "contacts": [asdict(c) for c in self.contacts],
        }
        path.write_text(json.dumps(payload, indent=2))
        return path

    def SummaryToJson(self, path: str | Path) -> Path:
        """Write the per-link summary as JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([asdict(s) for s in self.summary], indent=2))
        return path

    def Write(self, out_dir: str | Path) -> dict[str, Path]:
        """Write all three outputs into ``out_dir``."""
        out_dir = Path(out_dir)
        return {
            "csv": self.ToIonCsv(out_dir / "contactGraph.csv"),
            "json": self.ToJson(out_dir / "contactGraph.json"),
            "summary": self.SummaryToJson(out_dir / "summary.json"),
        }
