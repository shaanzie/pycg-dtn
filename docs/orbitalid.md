# Orbital IPs

Every node's default `eid` is an *orbital IP*: an address built from where
the node is, not just its name.

```
oip://bp7::v1::mars::sat::relay::2026-01-01T00:00:00::3778.19::0.001::93.0::0.0::0.0::0.0
└─┬─┘  └┬┘  └┬┘  └┬─┘ └┬┘ └──┬─┘  └───────────┬───────┘ └────────────┬────────────────┘
scheme  bp   ver  domain regime node-id     epoch                orbital state
```

`oip` (orbital IP) is a scheme name, a peer to BPv7's own `dtn`/`ipn` schemes
(RFC 9171 SS4.2.5.1). The two fields right after it are versions:

- `bp7` — the Bundle Protocol version the endpoint is reachable over
- `v1` — the version of this addressing scheme that produced the rest of the
  string

Either can change later without breaking addresses already in use.

## Scope prefix

`domain::regime::node-id` is a truncatable scope, coarsest first:

- **domain** — the node's clock domain (see {doc}`celestials`); every body
  in one planetary system shares one, e.g. `mars`
- **regime** — `body` for a natural body, `sat` for a satellite
- **node-id** — the slugified name

Everything sharing a domain shares that prefix: `mars` covers every node in
Mars's clock domain, `mars::sat` narrows that to satellites orbiting there.

## Orbital-state suffix

A satellite's address carries a trailing, opaque suffix: its epoch and
classical elements (semi-major axis, eccentricity, inclination, RAAN,
argument of periapsis, mean anomaly), in that order. A natural body has no
suffix — its position comes from SPICE, not a stored orbit.

The suffix is payload, not scope: two satellites in the same clock domain but
different orbits still share the same `domain::regime` prefix, and nothing
about the suffix is meant to be truncated over or queried by range (yet).

## Names are untouched

`eid` is a routing address; `name` is a display label, and the two are
independent. A satellite's `name` is exactly what you passed to
`AddSatellite`, and is what shows up in the visualizer's focus list and
click-to-select — see the **Addresses** tab in {doc}`visualizer` for the
`name` ↔ `eid` mapping of every node in a graph.

## Overriding it

Pass `eid=` to `AddCelestial` or `AddSatellite` to use your own scheme
instead — `ipn:4.1`, or anything else your bundle-protocol stack expects.
