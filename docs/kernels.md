# Kernels

A *kernel* is NAIF's term for a SPICE data file. Positions, body shapes, leap
seconds and gravitational parameters all come from kernels, and PyCG-DTN fetches
only the ones your scenario needs.

## What gets loaded

| Kernel | Provides | When |
|---|---|---|
| `naif0012.tls` | leap seconds, for UTC ↔ ephemeris time | always |
| `pck00011.tpc` | body radii and IAU body-fixed orientation | always |
| `de440s.bsp` | planetary ephemeris, 1849–2150 | always |
| `gm_de440.tpc` | gravitational parameters | any satellite |
| `mar099s.bsp` … | that system's satellites | per system |

Inspect the set for a scenario without downloading anything:

```python
cg.RequiredKernels()
```

```bash
pycg kernels --bodies Earth Mars Phobos
```

## How selection works

NAIF's ID codes are systematic — the leading digit of a three-digit code is the
planetary system — so the kernel needed for a body is derived from its ID rather
than looked up in a hand-maintained table. 

Two consequences worth knowing:

**The planetary ephemeris does not cover every planet body.** `de440s.bsp`
carries the Sun, Mercury, Venus, Earth, the Moon, and all the system
barycentres — but not the Mars, Jupiter, Saturn, Uranus, Neptune or Pluto body
centres. Asking for Mars therefore pulls in `mar099s.bsp`, even with no moons
involved.

**A satellite's central body is included automatically**, whether or not you
added it as a node, since its orbit cannot be placed otherwise.

## Coverage is verified

After loading, the kernels are checked against the bodies actually requested. If
something is missing you get a `KernelError` naming the bodies and the kernels
that were loaded, rather than a SPICE error thousands of evaluations later.

That check exists because NAIF's archive changes: satellite ephemerides are
periodically superseded and renamed. If a registered filename disappears
upstream, the download fails with a clear message.

## Caching

Kernels are cached in `kernel_dir` — `./kernels` by default — and never
re-downloaded once complete. 

```python
cg = ContactGraph(kernel_dir="/shared/spice")
```

See {doc}`installation` for sizes and for fetching ahead of time.
