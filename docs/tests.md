# Tests

```bash
pip install -e ".[dev]"
pytest -m "not network" -q
```

| Module | Tests | Covers |
|---|---:|---|
| `test_celestials.py` | 17 | name and ID resolution, systems, clock domains |
| `test_geometry.py` | 12 | window arithmetic, configuration validation |
| `test_graph.py` | 22 | building graphs, nodes, links, occulter selection |
| `test_kernels.py` | 18 | kernel selection and the registry |
| `test_linkbudget.py` | 18 | the Friis–Shannon chain and its parameters |
| `test_satellites.py` | 15 | orbital elements, validation, propagation |

## The network marker

Six tests are marked `network`. They download kernels from NAIF and check that
the assumptions baked into the registry still hold — that `de440s.bsp` really
does provide the bodies claimed for it, that a propagated ephemeris reproduces
its elements, that coverage extends past the analysed span.

```bash
pytest -q                 # everything, needs network
pytest -m "not network"   # offline, the default for development
pytest -m network         # only the ones that hit NAIF
```