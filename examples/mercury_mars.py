#!/usr/bin/env python3
# Contact plan for a Mercury-Mars link.


from pycg_dtn import ContactGraph

cg = ContactGraph()
cg.AddCelestial("Mercury")
cg.AddCelestial("Mars")

plan = cg.GenerateContactGraph(days=101) # Generate a contact plan for 101 days
plan.Write("out/mercury-mars")

link = plan.summary[0]
print(f"\n{len(plan)} contacts over 101 days")
print(f"in contact     {100 * link.contact_fraction:.1f}%")
print(f"longest outage {link.t_maxgap_days:.2f} d")
print(f"one-way light  {link.owlt_min_s / 60:.1f} - {link.owlt_max_s / 60:.1f} min")
