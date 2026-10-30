# LinkBudget

The link budget turns a distance into a data rate. Geometry decides *when* a
link exists; this decides *how fast* it is.

```python
lb = cg.GetLinkBudget()
lb.SetFrequency(32.0e9)     # Ka-band instead of X-band
lb.SetRxGain(79.0)          # a larger ground antenna
lb.SetBandwidth(5.0e6)
lb.SetMinRate(1000.0)       # drop contacts below 1 kbps
```

## The model

Free-space path loss (Friis) gives received power, that against the thermal
noise floor gives SNR, and Shannon gives capacity:

$$C = B \log_2(1 + \mathrm{SNR})$$

This is an upper bound, not a throughput prediction — no coding, modulation or
pointing loss is modelled. 

## Parameters

| Parameter | Getter / Setter | Default |
|---|---|---|
| Transmit power, W | `GetTxPower` / `SetTxPower` | 100 |
| Carrier, Hz | `GetFrequency` / `SetFrequency` | 8.42e9 (X-band) |
| Bandwidth, Hz | `GetBandwidth` / `SetBandwidth` | 1.0e6 |
| Transmit gain, dBi | `GetTxGain` / `SetTxGain` | 48 |
| Receive gain, dBi | `GetRxGain` / `SetRxGain` | 74.18 |
| Noise PSD, dBm/Hz | `GetNoisePsd` / `SetNoisePsd` | −174 |
| Noise temperature, K | `GetNoiseTemperature` / `SetNoiseTemperature` | 290 (same as the PSD) |
| Rate floor, bits/s | `GetMinRate` / `SetMinRate` | 1 |
| Rate cap, bits/s | `GetMaxRate` / `SetMaxRate` | none |

`SetNoiseTemperature(T)` sets the noise PSD to kT, so a receiver can be
described by its published system noise temperature. `max_rate_bps` caps the
Shannon rate at what the radio actually supports, e.g. its highest symbol rate.

The defaults model a spacecraft high-gain dish of roughly 3 m talking to a DSN
70 m ground antenna (74.18 dBi at X-band, [Rodemich
1989](https://ui.adsabs.harvard.edu/abs/1989TDAPR..97..314R/abstract)), against a
thermal noise floor of kT at 290 K.

Derived values have getters but no setters:

```python
lb.GetWavelength()    # metres, from the carrier
lb.GetNoisePower()    # dBm in band, from PSD and bandwidth
lb.RateBps(range_km)  # capacity at a distance, scalar or array
lb.AsDict()           # every parameter, embedded in output metadata
```

## What the defaults give you

| Distance | Rate |
|---|---:|
| Moon, 384,400 km | 21.1 Mbps |
| 0.5 AU | 5.9 Mbps |
| 1 AU | 4.0 Mbps |
| 2.5 AU | 1.8 Mbps |
| Jupiter, 5.2 AU | 0.6 Mbps |

Rate falls with the square of distance, which is why contacts get subdivided.

## Per-link radios

Real networks use different radios on different links: S-band between a lander
and a relay, Ka-band between the relay and Earth. Put nodes in **groups** and
give each pair of groups its own budget:

```python
cg.AddGroundStation("GOLDSTONE", "Earth", latitude_deg=35.43,
                    longitude_deg=-116.89, group="dsn")
cg.AddSatellite("RELAY", "Moon", semi_major_axis_km=11300.0, group="relay")

cg.SetLinkBudgetFor("dsn", "relay", uplink)     # dsn -> relay
cg.SetLinkBudgetFor("relay", "dsn", downlink)   # relay -> dsn
```

A budget applies to one direction. For a direction with no budget of its own,
the reverse direction's budget is used, then the default from
`GetLinkBudget()`. A node with no group is its own group, named after the node.
`SetNodeGroup(name, group)` changes it later.

Each direction gets its own rate, so a contact carries `rate_bps` (a to b) and
`rate_ba_bps` (b to a), and the ION plan lists each direction with its own
rate. A piece of a contact is kept only if both directions clear their rate
floor.

Link types that should never exist can be switched off:

```python
cg.DisableLinks("relay", "relay")   # no crosslinks
cg.GetDisabledLinks()               # [("relay", "relay")]
cg.EnableLinks("relay", "relay")
```

Every budget is recorded in the plan metadata under `link_budgets`.

## The rate floor

`min_rate_bps` discards contacts too slow to carry anything. The default of
1 bit/s only removes the degenerate cases; raise it to express a real
requirement:

```python
lb.SetMinRate(1000.0)   # ignore anything below 1 kbps
```

Contacts below the floor vanish from the plan entirely rather than appearing
with a tiny rate.

## Sub-contacts

A single visibility interval can span a large range change, so intervals are cut
wherever the achievable rate has drifted past a tolerance — 10% by default. Each
resulting sub-contact carries one representative rate that is accurate across
its own duration.

That is why a two-day Mercury–Mars window appears as several contacts rather than
one. The tolerance and sampling interval are on {doc}`geometry`
(`SetRateTolerance`, `SetRateSample`).