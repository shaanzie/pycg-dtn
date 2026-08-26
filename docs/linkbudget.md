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
| Rate floor, bits/s | `GetMinRate` / `SetMinRate` | 1 |

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