# Introduction

PyCG-DTN builds delay-tolerant networking contact plans from real ephemerides.

Give it a set of solar-system bodies, any satellites you define, and a number of
days. It works out which NAIF SPICE kernels those bodies need, downloads
them, computes when every pair of nodes can actually exchange data, and writes a
contact plan.

```python
from pycg_dtn import ContactGraph

cg = ContactGraph()
cg.AddCelestial("Earth")
cg.AddCelestial("Mars")
cg.AddSatellite("MRO-LIKE", "Mars", altitude_km=400, inclination_deg=93.0)

plan = cg.GenerateContactGraph(days=780)
plan.Write("out/")
```

A DTN contact plan says which nodes can talk, when, and how fast. The topology is dictated by where the planets happen to be, it
repeats on timescales of months to years. Two things take a deep-space link away even when both nodes are nominally in
view:

**Occultation** — a third body sits in the line of sight. Mars hides Phobos;
Jupiter hides Io; a planet hides its own orbiter once per revolution.

**Solar conjunction** — the signal path passes close to the Sun, whose corona
scatters and delays the signal badly enough that operators stand the link down.
The threshold is the Sun–Earth–probe angle; below roughly 3° the link is treated
as unusable, following DSN practice.

A **contact** is an interval during which two nodes can exchange data. Each surviving interval
is then cut into sub-contacts wherever the achievable data rate has drifted more
than a set tolerance, so that no single contact misrepresents how much data fits
through it.

## Where the numbers come from

Positions come from SPICE, NAIF's toolkit for solar-system geometry. A *kernel*
is NAIF's term for one of its data files — the planetary ephemeris, body radii
and orientation, leap seconds. PyCG-DTN resolves which kernels your bodies
require, fetches only those, and verifies they cover what was asked for.

Occultation and conjunction are found with SPICE's own geometry-finder routines
rather than by sampling, so interval boundaries are solved for rather than
rounded to a step size.

Data rates come from a Friis free-space path loss - SNR - Shannon capacity
chain. The defaults model an X-band spacecraft high-gain dish talking to a DSN
70 m antenna, and every parameter is configurable.

Satellites are yours to define. Spacecraft manoeuvre, so unlike planets there is
no generic kernel carrying their trajectories; you supply a Keplerian orbit and
it is propagated as two-body motion into the same geometry pipeline.

## Output

Plans are written in three forms: an ION contact plan CSV, ingestible by NASA
JPL's reference DTN implementation; a JSON plan carrying every contact with full
metadata; and a per-link summary whose most useful figure is the longest outage,
the interval a bundle has to survive.

## Where to go next

- {doc}`installation` — installing the package and its kernels
- {doc}`celestials` — adding natural bodies as nodes
- {doc}`satellites` — defining spacecraft from orbital elements
- {doc}`contactgraph` — building and configuring a graph
- {doc}`contactplan` — reading and writing the result
