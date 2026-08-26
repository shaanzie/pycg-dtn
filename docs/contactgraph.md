# ContactGraph

`ContactGraph` is the builder. Add nodes, configure the models if you want to,
then generate a plan.

```python
from pycg_dtn import ContactGraph

cg = ContactGraph()
cg.AddCelestial("Earth")
cg.AddCelestial("Mars")
cg.AddSatellite("MRO-LIKE", "Mars", altitude_km=400, inclination_deg=93.0)

plan = cg.GenerateContactGraph(days=780)
```

## Constructing

```python
cg = ContactGraph(
    kernel_dir="/shared/spice",   # default: ./kernels
    link_budget=LinkBudget(),     # default: X-band to a DSN 70 m
    geometry=GeometryConfig(),    # default: 3 deg solar exclusion
)
```

All three are optional.

## Adding nodes

{doc}`celestials` covers natural bodies, {doc}`satellites` covers spacecraft.
Both become nodes of the same kind, and every unordered pair of nodes becomes a
link:

```python
cg.GetCelestials()   # natural bodies, in the order added
cg.GetSatellites()   # artificial satellites
cg.GetNodes()        # both
cg.GetLinks()        # every unordered pair
cg.LinkKind(a, b)    # "intra" if the two share a clock domain, else "inter"
```

## Configuring

```python
cg.GetLinkBudget().SetFrequency(32.0e9)
cg.GetGeometry().SetSepExclusion(2.0)
```

Or replace either wholesale with `SetLinkBudget()` / `SetGeometry()`. See
{doc}`linkbudget` and {doc}`geometry`.

## Kernels

Usually you can ignore these — generating fetches what it needs. To look or
fetch ahead:

```python
cg.RequiredKernels()    # what this scenario needs, downloads nothing
cg.FetchKernels()       # download whatever is missing
```

See {doc}`kernels`.

## Generating

```python
plan = cg.GenerateContactGraph(
    days=780,                          # required
    start="2026-01-01T00:00:00",       # UTC, default as shown
    fetch=True,                        # download missing kernels
    progress=True,                     # print progress
)
```

Returns a {doc}`contactplan`. Set `fetch=False` to fail rather than download,
and `progress=False` to run quietly.

A graph needs at least two nodes and a positive `days`, or it raises
`ContactGraphError`.

## A note on span

Contact plans repeat on the **synodic period** — the time for two bodies to
return to the same relative arrangement. For orbital periods `Pa` and `Pb` that
is `1 / |1/Pa − 1/Pb|`. Anything longer than one synodic period mostly repeats
what you already have.
