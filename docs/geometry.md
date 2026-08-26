# Geometry

Geometry decides *when* two nodes can see each other. Two things take a link away:

**Occultation** — a third body sits in the line of sight.

**Solar conjunction** — the path passes close enough to the Sun that its corona
scatters and delays the signal beyond use.

## Occultation

Occultation is found with SPICE's `gfoclt`, which models the occulting body as
its reference ellipsoid in that body's frame, and applies light-time correction. 

Artificial satellites are treated as point targets: they are occulted, but they
never occult anything. A spacecraft is far too small to shadow a link.

## Solar conjunction

The Sun is handled separately, because what matters is not whether the Sun's disc
blocks the path but whether the path passes through the corona around it.

The threshold is expressed as the **Sun–Earth–probe angle** (SEP): the angle at
the Sun between the two endpoints. Below roughly 3° the link is treated as
unusable, following DSN practice ([DSN handbook
810-005](https://deepspace.jpl.nasa.gov/dsndocs/810-005/106/106B.pdf)).

Conjunction is what produces the long outages in an interplanetary plan. A
Mercury–Mars link over one synodic period is in contact 95.8% of the time, and
essentially all of the remaining 4.2% is a single conjunction lasting days.

## Configuring the search

Every parameter has a getter and a setter on `cg.GetGeometry()`. Setters validate
and chain.

```python
geo = cg.GetGeometry()
geo.SetSepExclusion(2.0)     # tighter solar exclusion, degrees
geo.SetOccultStep(300.0)     # finer occultation search, seconds
geo.SetRateTolerance(0.05)   # split contacts on 5% rate drift
```

| Parameter | Getter / Setter | Default |
|---|---|---|
| Occultation search step, s | `GetOccultStep` / `SetOccultStep` | 600 |
| Conjunction search step, s | `GetCoronaStep` / `SetCoronaStep` | 21600 |
| Prefilter sampling step, s | `GetPrefilterStep` / `SetPrefilterStep` | 1800 |
| Prefilter margin, radii | `GetPrefilterMargin` / `SetPrefilterMargin` | 3 |
| SEP exclusion, degrees | `GetSepExclusion` / `SetSepExclusion` | 3 |
| Rate sampling interval, s | `GetRateSample` / `SetRateSample` | 3600 |
| Rate drift tolerance | `GetRateTolerance` / `SetRateTolerance` | 0.10 |

`GetCoronaExclusionKm()` is derived from the SEP angle and has no setter; set the
angle instead. `AsDict()` returns every parameter, and is what gets embedded in
the output metadata so a plan records the settings that produced it.