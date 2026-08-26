#!/usr/bin/env python3
# Contact plan for a Mercury-Mars link, relayed by a Mars orbiter.


from pycg_dtn import ContactGraph

cg = ContactGraph()
cg.AddCelestial("Mercury")
cg.AddCelestial("Mars")
cg.AddSatellite("MRO", "Mars", altitude_km=400, eccentricity=0.001,
                inclination_deg=93.0)

plan = cg.GenerateContactGraph(days=101) # Generate a contact plan for 101 days
plan.Write("out/mercury-mars")

print(f"\n{len(plan)} contacts over 101 days")
for s in plan.summary:
    print(f"{s.a:<10}{s.b:<10}{s.kind:<6}"
          f"in contact {100 * s.contact_fraction:5.1f}%   "
          f"longest outage {s.t_maxgap_days:6.2f} d   "
          f"one-way light {s.owlt_min_s / 60:.1f} - {s.owlt_max_s / 60:.1f} min")
