# Tests

```bash
pip install -e ".[dev]"
pytest -m "not network" -q
```

| Module | Tests | Covers |
|---|---:|---|
| `test_bundletrace.py` | 18 | bundle trace loading and validation |
| `test_celestials.py` | 17 | name and ID resolution, systems, clock domains |
| `test_geometry.py` | 12 | window arithmetic, configuration validation |
| `test_graph.py` | 28 | building graphs, nodes, links, groups, per-link budgets |
| `test_kernels.py` | 18 | kernel selection and the registry |
| `test_linkbudget.py` | 23 | the Friis–Shannon chain, rate cap, noise temperature |
| `test_plan.py` | 2 | per-direction rates in the ION plan |
| `test_satellites.py` | 15 | orbital elements, validation, propagation |
| `test_stations.py` | 13 | ground stations, elevation masks, asymmetric links |
| `test_visualize.py` | 16 | the HTML viewer payload |

## The network marker

23 tests are marked `network`. They download kernels from NAIF and check that
the assumptions baked into the registry still hold — that `de440s.bsp` really
does provide the bodies claimed for it, that a propagated ephemeris reproduces
its elements, that coverage extends past the analysed span.

```bash
pytest -q                 # everything, needs network
pytest -m "not network"   # offline, the default for development
pytest -m network         # only the ones that hit NAIF
```