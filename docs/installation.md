# Installation

```bash
pip install pycg-dtn
```

Requires Python 3.10 or newer. Three runtime dependencies are pulled in
automatically: [NumPy](https://numpy.org), [SpiceyPy](https://spiceypy.readthedocs.io)
(the Python binding to NAIF's SPICE toolkit), and
[Requests](https://requests.readthedocs.io).

Installing also puts a `pycg` command on your path:

```bash
pycg --version
```

## Kernels are not bundled

SPICE kernels are fetched from [NAIF's public archive](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/) the
first time a scenario needs them, and cached in a `kernels/` directory in your
working directory.

Only the kernels your bodies actually require are downloaded. 

| Kernel | Size | Needed for |
|---|---:|---|
| `naif0012.tls` | 5 KB | always — leap seconds |
| `pck00011.tpc` | 128 KB | always — body radii and orientation |
| `gm_de440.tpc` | 12 KB | any satellite — gravitational parameters |
| `de440s.bsp` | 31 MB | always — planetary ephemeris |
| `mar099s.bsp` | 65 MB | Mars satellites |
| `nep097.bsp` | 100 MB | Neptune satellites |
| `plu060.bsp` | 129 MB | Pluto system |
| `sat441.bsp` | 631 MB | Saturn satellites |
| `ura116xl.bsp` | 660 MB | Uranus satellites |
| `jup365.bsp` | 1.08 GB | Jovian satellites |

### Check the cost first

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

This never downloads anything. `[have]` means the file is already cached.

### Fetch ahead of time

```bash
pycg fetch --bodies Earth Mars Phobos
```

### Choosing where kernels live

By default that is `./kernels`. Point it anywhere:

```python
cg = ContactGraph(kernel_dir="/shared/spice")
```

```bash
pycg build --bodies Earth Mars --days 780 --kernel-dir /shared/spice
```

## Installing from source

```bash
git clone https://github.com/shaanzie/pycg-dtn.git
cd pycg-dtn
pip install -e ".[dev]"
```

## Verifying

```bash
pytest -m "not network" -q
```