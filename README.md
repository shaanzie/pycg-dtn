# PyCG-DTN

[![Documentation](https://readthedocs.org/projects/pycg-dtn/badge/?version=latest)](https://pycg-dtn.readthedocs.io/en/latest/)
[![PyPI](https://img.shields.io/pypi/v/pycg-dtn)](https://pypi.org/project/pycg-dtn/)

Build DTN contact graphs for deep-space networks from real ephemerides.

Give it a set of bodies and a number of days. It works out which SPICE kernels it
needs, downloads them from NASA/NAIF, computes when every pair of nodes can
actually see each other, and writes a contact plan.

```python
from pycg_dtn import ContactGraph

cg = ContactGraph()
cg.AddCelestial("Earth")
cg.AddCelestial("Mars")
cg.AddSatellite("MRO-LIKE", "Mars", altitude_km=400, inclination_deg=93.0)

plan = cg.GenerateContactGraph(days=780)
plan.Write("out/")
```

```
out/contactGraph.csv     ION contact plan
out/contactGraph.json    full plan with metadata
out/summary.json         per-link statistics
```

## Install

```bash
pip install pycg-dtn
```

Requires Python 3.10+.

Full documentation: **[pycg-dtn.readthedocs.io](https://pycg-dtn.readthedocs.io/)**

## What it computes

A **contact** is an interval during which two nodes can exchange data. Two things
take a deep-space link away even when both endpoints are nominally in view:

**Occultation** — a third body sits in the line of sight. Mars hides Phobos; Jupiter
hides Io. 

**Solar conjunction** — the signal path passes close to the Sun, whose corona
scatters and delays the signal badly enough that operators stand the link down.
The threshold is the Sun–Earth–probe angle; below about 3° the link is treated as
unusable, following DSN practice ([DSN handbook
810-005](https://deepspace.jpl.nasa.gov/dsndocs/810-005/106/106B.pdf)).

Contact time is the analysed span minus the union of everything that blocks it.
Each surviving interval is then cut into sub-contacts wherever the achievable data
rate has drifted more than 10%, so no single contact misrepresents how much data
fits through it.

Rates come from a Friis free-space path loss → SNR → Shannon capacity chain, with
defaults modelling an X-band spacecraft high-gain dish talking to a DSN 70 m
antenna (74.18 dBi, [Rodemich
1989](https://ui.adsabs.harvard.edu/abs/1989TDAPR..97..314R/abstract)).

## Bodies

`AddCelestial` accepts anything NAIF names, case-insensitively — or a NAIF integer
ID code.

```python
cg.AddCelestial("Titan")
cg.AddCelestial("Europa", eid="ipn:5.2")   # custom ION endpoint identifier
cg.AddCelestial("401")                      # Phobos, by ID
```

An unrecognised name raises `UnknownCelestialBodyError`.

## Satellites

Satellites here are defined by you, as a classical Keplerian orbit about a central body:

```python
cg.AddSatellite("MRO-LIKE", "Mars", altitude_km=400,
                eccentricity=0.001, inclination_deg=93.0)
```

Size the orbit with either `altitude_km` (above the central body's equatorial
radius) or `semi_major_axis_km`, and give exactly one of them. The rest —
`eccentricity`, `inclination_deg`, `raan_deg`, `arg_periapsis_deg`,
`mean_anomaly_deg`, `epoch_utc` — default to a circular orbit at the
start epoch.

A satellite is a node like any other. It is treated as a point target, so it never occults anything, but
things certainly occult it, a low orbiter is hidden by its own planet once per
revolution, which is what dominates its contact plan:

```
MERCURY   MARS      inter in contact  95.8%   longest outage   4.27 d
MERCURY   MRO-LIKE  inter in contact  71.5%   longest outage   4.27 d
MARS      MRO-LIKE  intra in contact 100.0%   longest outage   0.00 d
```

## Kernels

A *kernel* is NAIF's term for a SPICE data file. Only the ones your bodies need are
downloaded, which matters — the Jovian satellite ephemeris alone is over a
gigabyte, and an Earth–Mars scenario should never pay for it.

Check the cost before committing:

```bash
pycg kernels --bodies Earth Mars Phobos
```

```
kernel directory: /home/you/kernels
4 kernels, about 96 MB total

  [need] naif0012.tls          0.0 MB   leap seconds, for UTC <-> ET conversion
  [need] pck00011.tpc          0.1 MB   body radii and IAU body-fixed orientation
  [need] de440s.bsp           31.2 MB   planetary ephemeris DE440 (short), 1849-2150
  [need] mar099s.bsp          64.5 MB   Phobos and Deimos
```
All files come from [NAIF's public generic-kernel
archive](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/).

## Configuring the link budget

Every radio parameter has a getter and a setter. Setters chain and validate.

```python
lb = cg.GetLinkBudget()
lb.SetFrequency(32.0e9)     # Ka-band instead of X-band
lb.SetRxGain(79.0)          # a larger ground antenna
lb.SetBandwidth(5.0e6)
lb.SetMinRate(1000.0)       # drop contacts below 1 kbps

print(lb.GetWavelength(), lb.GetNoisePower())
```

| Parameter | Getter / Setter | Default |
|---|---|---|
| Transmit power, W | `GetTxPower` / `SetTxPower` | 100 |
| Carrier, Hz | `GetFrequency` / `SetFrequency` | 8.42e9 (X-band) |
| Bandwidth, Hz | `GetBandwidth` / `SetBandwidth` | 1.0e6 |
| Transmit gain, dBi | `GetTxGain` / `SetTxGain` | 48 |
| Receive gain, dBi | `GetRxGain` / `SetRxGain` | 74.18 |
| Noise PSD, dBm/Hz | `GetNoisePsd` / `SetNoisePsd` | −174 |
| Rate floor, bits/s | `GetMinRate` / `SetMinRate` | 1 |

## Configuring the geometry search

Same pattern on `cg.GetGeometry()`:

```python
geo = cg.GetGeometry()
geo.SetSepExclusion(2.0)     # tighter solar exclusion, degrees
geo.SetOccultStep(300.0)     # finer occultation search, seconds
geo.SetRateTolerance(0.05)   # split contacts on 5% rate drift
```

## Choosing a span

Contact plans repeat on the **synodic period** — the time for two bodies to
return to the same relative arrangement, which for planets with orbital periods
`Pa` and `Pb` is `1 / |1/Pa − 1/Pb|`. 

## Reading the results

```python
plan = cg.GenerateContactGraph(days=780)

len(plan)                          # number of contacts
plan.ForLink("EARTH", "MARS")      # contacts on one link, time-ordered

for s in plan.LongestOutages(5):
    print(s.a, s.b, s.t_maxgap_days)
```

The CSV is the contact plan format ingested by [ION](https://github.com/nasa-jpl/ION-DTN),
NASA JPL's reference DTN implementation. Each contact becomes four rows — a
`contact` and a `range` line in each direction.

## Command line

```bash
pycg kernels --bodies Earth Mars Phobos
pycg fetch   --bodies Earth Mars Phobos
pycg build   --bodies Earth Mars --days 780 --out out/
pycg build   --bodies Earth Mars --days 780 --frequency 32e9 --rx-gain 79
```

Satellites take a `NAME,CENTRAL,key=value,...` spec and the flag repeats:

```bash
pycg build --bodies Earth Mars --days 780 \
           --satellite RELAY-1,Mars,alt=400,inc=93 \
           --satellite RELAY-2,Mars,sma=20000,ecc=0.3
```

Keys are `alt` or `sma` (give one), `ecc`, `inc`, `raan`, `argp`, `ma`, `eid`.
The central body does not have to be a node — it still occults its own orbiter.

## Citing

If you use PyCG-DTN in published work, please cite it.

```bibtex
@software{lagwankar_pycg_dtn,
  author  = {Lagwankar, Ishaan and Klevering, Griffin},
  title   = {{PyCG-DTN}: {DTN} contact graphs for deep-space networks
             from {SPICE} ephemerides},
  version = {1.0.0},
  year    = {2026},
  license = {GPL-3.0-or-later},
  url     = {https://github.com/shaanzie/pycg-dtn}
}
```

## License

GNU General Public License v3.0 or later. See [LICENSE](LICENSE).
