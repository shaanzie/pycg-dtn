#!/usr/bin/env python3

import json
from pathlib import Path

import spiceypy as sp

from pycg_dtn import ContactGraph

OUT = Path("out/solar-system")
START = "2026-06-01T00:00:00"
DAYS = 10

cg = ContactGraph()
for body in ("Mercury", "Venus", "Earth", "Mars"):
    cg.AddCelestial(body)

cg.AddSatellite("SATALIGHT", "Earth", altitude_km=800, inclination_deg=98.0)

plan = cg.GenerateContactGraph(days=DAYS, start=START)

ROUTE = [("MERCURY", "VENUS"), ("VENUS", "SATALIGHT"), ("SATALIGHT", "MARS")]
EID = {n.name: n.eid for n in cg.GetNodes()}

hops = []
at = plan.start_et
for src, dst in ROUTE:
    options = [c for c in plan.ForLink(src, dst) if c.stop_et > at]
    if not options:
        raise SystemExit(f"no contact on {src} -> {dst} after the previous hop")
    c = options[0]
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

trace = {
    "meta": {"run": "inner-solar-system", "start_utc": plan.start_utc},
    "bundles": [{
        "id": "bundle-0001",
        "source": EID["MERCURY"],
        "destination": EID["MARS"],
        "created_utc": plan.start_utc,
        "size_bytes": 1_000_000,
        "hops": hops,
    }],
}

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "bundle-trace.json").write_text(json.dumps(trace, indent=2))

html = cg.GenerateVisualizer(
    600,
    out=OUT / "visualizer.html",
    trace=OUT / "bundle-trace.json",
    title="Inner solar system",
)

print(f"\n{len(plan)} contacts over {DAYS} days")
for s in plan.summary:
    print(f"  {s.a:<13}{s.b:<13}{s.kind:<6}{100 * s.contact_fraction:5.1f}% in contact")

print(f"\nbundle Mercury -> Mars, {len(hops)} hops")
for i, h in enumerate(hops, 1):
    print(f"  {i}. {h['from']:<18}-> {h['to']:<18}"
          f"owlt {h['owlt_s'] / 60:6.1f} min   {h['tx_start_utc']}")

print(f"\nwrote {html}")
