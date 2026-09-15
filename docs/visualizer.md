# Visualizer

`GenerateVisualizer` writes a single HTML file showing the graph in 3D, with a
second tab for {doc}`bundletrace`.

```python
cg.GenerateContactGraph(days=10, start="2026-06-01T00:00:00")
cg.GenerateVisualizer(600, out="out/visualizer.html")
```

`step_size` is how far one press of the right arrow advances time, in seconds.
It uses the plan from the last `GenerateContactGraph`; pass `days=` instead to
generate one on the spot.

| Argument | Meaning |
|---|---|
| `step_size` | seconds advanced per arrow press |
| `out` | where to write, default `out/visualizer.html` |
| `trace` | a `bundle-trace.json` to populate the bundle tab |
| `title` | page title |
| `days`, `start` | only used when there is no plan yet |

- focus the **Sun** and the view frames every planetary orbit
- focus a **planet** and it reframes to whatever orbits that planet

## Satellites

Satellites are grey and their orbits hidden by default. Selected satellites and their orbits are drawn *after* the planets, so an orbit
close to the surface is not hidden by the disc beneath it.

## Choosing a step size

```python
sat = cg.AddSatellite("RELAY", "Mars", altitude_km=400)
sat.elements.PeriodSeconds() / 8      # a step that reads smoothly, usually a synodic period
```

## Colours

Natural bodies are roughly standard colours, the Sun yellow, Earth blue, Mars
rust. Anything unrecognised falls back to grey, as do satellites until selected.

The Sun is always drawn, and the body a node orbits is included even when it is
not a node of the graph, since the node cannot be placed without it — a
satellite's central body, a moon's planet, and so on up the chain.

## What orbits what

Each node's orbit is drawn about the body it actually orbits: a moon about its
planet, a planet about the Sun, a satellite about its central body. So Phobos
traces a 9,400 km ellipse around Mars rather than Mars's own path around the
Sun. The Sun itself is drawn without an orbit.

An orbit longer than the plan is still drawn whole — a satellite with a
year-long period gets a full revolution, not the slice the plan happens to
cover.
