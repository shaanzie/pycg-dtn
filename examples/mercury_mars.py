#!/usr/bin/env python3
# Contact plan for a Mercury-Mars link, relayed by a Mars orbiter.

import json
from pathlib import Path

import spiceypy as sp

from pycg_dtn import ContactGraph

OUT = Path("out/mercury-mars")

cg = ContactGraph()
cg.AddCelestial("Mercury")
cg.AddCelestial("Mars")
cg.AddSatellite("MRO", "Mars", altitude_km=400, eccentricity=0.001,
                inclination_deg=93.0)

plan = cg.GenerateContactGraph(days=101) # Generate a contact plan for 101 days
plan.Write(OUT)

ROUTE = [("MERCURY", "MRO"), ("MRO", "MARS")]
EID = {n.name: n.eid for n in cg.GetNodes()}

hops = []
at = plan.start_et
for src, dst in ROUTE:
    c = next(c for c in plan.ForLink(src, dst) if c.stop_et > at)
    tx = max(at, c.start_et)
    duration = min(8e6 / c.rate_bps, c.stop_et - tx)
    hops.append({
        "from": EID[src],
        "to": EID[dst],
        "tx_start_utc": sp.et2utc(tx, "ISOC", 0),
        "tx_stop_utc": sp.et2utc(tx + duration, "ISOC", 0),
        "rx_utc": sp.et2utc(tx + duration + c.owlt_s, "ISOC", 0),
        "owlt_s": round(c.owlt_s, 1),
        "status": "delivered" if dst == "MARS" else "forwarded",
    })
    at = tx + duration + c.owlt_s

(OUT / "bundle-trace.json").write_text(json.dumps({
    "meta": {"run": "mercury-mars", "start_utc": plan.start_utc},
    "bundles": [{
        "id": "bundle-0001",
        "source": EID["MERCURY"],
        "destination": EID["MARS"],
        "created_utc": plan.start_utc,
        "size_bytes": 1_000_000,
        "hops": hops,
    }],
}, indent=2))

html = cg.GenerateVisualizer(
    6 * 3600,
    out=OUT / "visualizer.html",
    trace=OUT / "bundle-trace.json",
    title="Mercury-Mars",
)

print(f"\nwrote {html}")
