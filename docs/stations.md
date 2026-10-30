# Ground stations

A *ground station* is a fixed site on the surface of a body: a DSN antenna on
Earth, a lander at the lunar south pole. It turns with its body, and it can only
see what is above its local horizon.

```python
cg.AddGroundStation("GOLDSTONE", "Earth",
                    latitude_deg=35.4259,
                    longitude_deg=-116.8895,
                    altitude_km=1.0,
                    min_elevation_deg=10.0)
```

## Defining a site

| Parameter | Meaning | Default |
|---|---|---|
| `latitude_deg` | geodetic latitude, degrees | required |
| `longitude_deg` | east-positive longitude, degrees | required |
| `altitude_km` | height above the reference ellipsoid | 0.0 |
| `min_elevation_deg` | elevation mask: targets below it are not visible | 0.0 |
| `eid` | ION endpoint identifier | `dtn:` plus the slugified name |
| `group` | group for per-link radios, see {doc}`linkbudget` | the station's own name |

Coordinates are in the body's IAU frame (`IAU_EARTH`, `IAU_MOON`, ...), from
`pck00011.tpc`. A latitude outside [-90, 90] or a mask outside [-90, 90) raises
`GroundStationError`.

## How it is placed

The site's position is constant in the body-fixed frame, so it is written to
SPICE as an SPK segment in that frame and SPICE rotates it with the body. This
is how NAIF's own DSN station kernels work
([generic_kernels/spk/stations](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/stations/)).

Compared with NAIF's DSS-14 topocentric frame (ITRF93 with high-precision Earth
orientation), the elevation of the Moon from a station at DSS-14's coordinates
agrees to within 0.07 deg. The difference is the simpler IAU rotation model.

## What a station can see

- **Its own body** is not treated as an occulter. The elevation mask decides
  when a target is above the horizon.
- **Other bodies** still occult as usual, e.g. the Moon hiding a relay from a
  DSN site.
- **Two stations on the same body** are never linked; ground networks are
  outside the model.
- A link between stations on two different bodies (e.g. a DSN site and a lunar
  lander) needs both masks to be clear.

The elevation search steps through time with `GeometryConfig.SetElevationStep`
(60 s by default). It must be shorter than the shortest pass you want to catch.

## A station is a node

```python
cg.GetStations()     # ground stations, in the order added
cg.GetNodes()        # celestials, satellites, then stations
```

It shares the clock domain of its body, so a DSN site and an Earth orbiter are
`"intra"`, and a DSN site and a lunar lander are `"inter"`.

From the command line:

```bash
pycg build --bodies Moon --station "GOLDSTONE,Earth,lat=35.43,lon=-116.89,el=10" --days 2
```
