#!/usr/bin/env python3
# Two relays in solar orbit, reaching Venus and Mercury behind the Sun.
#
# On 2029-03-26 Venus and Mercury both sit within the 3 degree solar exclusion
# as seen from Earth, so Earth cannot reach either directly. Two relays at 1 AU,
# a quarter turn either side of Earth, can see both, and give a two-hop path.

from pathlib import Path

from pycg_dtn import ContactGraph

OUT = Path("out/solar-relays")
START = "2029-03-26T00:00:00"
AU = 149_597_870.7

cg = ContactGraph()
for body in ("Earth", "Venus", "Mercury", "Mars"):
    cg.AddCelestial(body)

# Earth is at mean anomaly 185.2 deg on the start date; the inclination is the
# J2000 obliquity, so the relays orbit in the ecliptic.
for name, phase in (("RELAY-A", 275.2), ("RELAY-B", 95.2)):
    cg.AddSatellite(name, "Sun", semi_major_axis_km=AU,
                    inclination_deg=23.439279, mean_anomaly_deg=phase,
                    epoch_utc=START)

plan = cg.GenerateContactGraph(days=3, start=START)
plan.Write(OUT)

for s in sorted(plan.summary, key=lambda x: (x.a, x.b)):
    print(f"{s.a:<9}{s.b:<9}{'open' if s.n_contacts else 'never opens'}")

html = cg.GenerateVisualizer(3600, out=OUT / "visualizer.html",
                             title="Solar relays")
print(f"wrote {html}")
