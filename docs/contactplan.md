# ContactPlan

`GenerateContactGraph` returns a `ContactPlan`: the contacts, a per-link summary,
and the metadata describing how they were produced.

```python
plan = cg.GenerateContactGraph(days=780)

len(plan)                       # number of contacts
for contact in plan: ...        # iterates contacts
plan.start_utc, plan.stop_utc   # ISO strings for the analysed span
```

## Contacts

A `Contact` is one interval during which two nodes can exchange data at a
roughly constant rate.

| Field | Meaning |
|---|---|
| `a`, `b` | node names |
| `a_eid`, `b_eid` | ION endpoint identifiers |
| `kind` | `"intra"` or `"inter"` clock domain |
| `start_et`, `stop_et` | span, in SPICE ephemeris seconds |
| `rate_bps` | representative rate across this contact |
| `owlt_s` | one-way light time, mean |
| `owlt_min_s`, `owlt_max_s` | one-way light time, range |
| `range_min_km`, `range_max_km` | distance range |
| `duration_s` | derived |
| `volume_bits` | derived: rate × duration |

`volume_bits` is the useful one for sizing — how much actually fits through a
single contact.

Filter to one link:

```python
plan.ForLink("EARTH", "MARS")   # either direction, time-ordered
```

## Per-link summary

`plan.summary` holds one `LinkSummary` per link:

| Field | Meaning |
|---|---|
| `a`, `b`, `kind` | the link |
| `blockers` | bodies that actually occulted it |
| `n_contacts`, `n_outages` | counts |
| `contact_days`, `contact_fraction` | time in contact |
| `t_maxgap_days` | **longest single outage** |
| `owlt_min_s`, `owlt_max_s` | light-time range |

`t_maxgap_days` is usually the number that matters: it is the interval a bundle
has to survive, and so sets storage and lifetime requirements.

```python
for s in plan.LongestOutages(5):
    print(s.a, s.b, s.t_maxgap_days)
```

## Writing it out

```python
plan.Write("out/")
```

```
out/contactGraph.csv     ION contact plan
out/contactGraph.json    every contact, with metadata
out/summary.json         per-link statistics
```

Or write one at a time with `ToIonCsv()`, `ToJson()`, `SummaryToJson()`. Each
returns the path written.

### The ION CSV

The CSV is the contact plan format read by
[ION](https://github.com/nasa-jpl/ION-DTN), NASA JPL's reference DTN
implementation:

```
a contact +0 +86400 dtn:earth dtn:mars 3990000
a range   +0 +86400 dtn:earth dtn:mars 1246.331
```

Times are seconds relative to the start of the plan, not absolute. Every contact
becomes four rows — a `contact` and a `range` line in each direction — because
ION treats the two directions separately.

### The JSON

`contactGraph.json` carries every contact plus a `meta` block recording the
span, the nodes, the kernels used, and the full link-budget and geometry
settings. A plan therefore records the configuration that produced it, which is
what makes a run reproducible.