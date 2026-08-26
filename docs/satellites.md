# Satellites

A *satellite* is an artificial body you define. Unlike planets, spacecraft
manoeuvre, so no generic kernel carries their trajectories — you supply an orbit
and it is propagated into the same geometry pipeline.

```python
cg.AddSatellite("MRO-LIKE", "Mars",
                altitude_km=400,
                eccentricity=0.001,
                inclination_deg=93.0)
```

## Defining an orbit

Size the orbit with **exactly one** of:

- `altitude_km` — height of periapsis above the central body's equatorial radius
- `semi_major_axis_km` — the semi-major axis directly

Giving both, or neither, raises `SatelliteError`.

Everything else is optional and defaults to a circular equatorial orbit:

| Parameter | Default |
|---|---|
| `eccentricity` | 0.0 |
| `inclination_deg` | 0.0 |
| `raan_deg` | 0.0 |
| `arg_periapsis_deg` | 0.0 |
| `mean_anomaly_deg` | 0.0 |
| `epoch_utc` | the graph's start epoch |
| `eid` | `dtn:` plus the slugified name |

Angles are degrees, distances kilometres. `epoch_utc` is the epoch that
`mean_anomaly_deg` refers to.

## A satellite is a node

It joins the graph like any celestial and links to every other node. 

```python
mars = cg.AddCelestial("Mars")
sat  = cg.AddSatellite("RELAY", "Mars", altitude_km=400)

cg.LinkKind(mars, sat)    # "intra"
sat.domain                # "mars"
```

## Occultation

Satellites are point targets: they are occulted, but never occult anything. A
spacecraft is far too small to shadow a link.

What dominates a low orbiter's plan is its own planet, which hides it once per
revolution:

```
MERCURY   MARS   inter  in contact  95.8%   longest outage 4.27 d
MERCURY   MRO    inter  in contact  71.5%   longest outage 4.27 d
MARS      MRO    intra  in contact 100.0%   longest outage 0.00 d
```

The orbiter loses about a quarter of the time the direct link has, all of it in
short per-orbit gaps. Its link to Mars itself is uninterrupted — a planet cannot
occult its own satellite as seen from that planet.

## Validation

`SatelliteError` is raised for:

- an unknown central body
- a periapsis inside the central body — the orbit intersects the surface
- `eccentricity` outside `[0, 1)` — an open orbit never returns
- `inclination_deg` outside `[0, 180]`
- a non-positive semi-major axis
- a duplicate satellite name

See {doc}`propagation` for how the orbit is turned into an ephemeris, and what
that model does not capture.
