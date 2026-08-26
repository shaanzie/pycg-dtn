# Celestials

A *celestial* is a natural body — a planet, a moon, or the Sun — used as a node
in the contact graph. Add one by name:

```python
cg = ContactGraph()
cg.AddCelestial("Earth")
cg.AddCelestial("Mars")
cg.AddCelestial("Phobos")
```

## Naming

Names are resolved against SPICE's own body table, which the toolkit carries
built in — no kernel is needed to look one up. Matching is case-insensitive, and
a NAIF integer ID code works as well as a name:

```python
cg.AddCelestial("Titan")     # TITAN,  606
cg.AddCelestial("io")        # IO,     501
cg.AddCelestial("401")       # PHOBOS, 401
```

Names are canonicalised to upper case, so `"mars"`, `"Mars"` and `"499"` all give
the same body. 

## NAIF ID codes

Every body SPICE knows has an integer code, and the numbering is systematic:

| Code | Meaning | Examples |
|---|---|---|
| `10` | the Sun | |
| `1`–`9` | planetary system barycentres | `4` Mars barycentre |
| `N99` | the planet itself | `399` Earth, `499` Mars, `599` Jupiter |
| `N01`–`N98` | that planet's satellites | `301` Moon, `401` Phobos, `501` Io |


## Endpoint identifiers

Every node carries an ION endpoint identifier, written into the contact plan.
The default is `dtn:` plus the lower-cased name:

```python
resolve("Mars").eid                    # "dtn:mars"
resolve("Europa", eid="ipn:5.2").eid   # "ipn:5.2"
```

Pass `eid=` to `AddCelestial` to override it, which is what you want when the
plan has to line up with an existing ION configuration.

## Duplicates

A body can only be added once, and that is enforced on the NAIF ID rather than
the string, so aliases are caught too:

```python
cg.AddCelestial("Mars")
cg.AddCelestial("mars")    # UnknownCelestialBodyError: already in the graph
cg.AddCelestial("499")     # likewise
```
