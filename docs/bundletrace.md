# Bundle trace

A **bundle trace** is that run's record of where each bundle actually went, and the {doc}`visualizer` reads it
back as a timeline.

```python
from pycg_dtn import bundletrace

trace = bundletrace.load("bundle-trace.json")
b = trace.Get("bundle-0001")
b.n_hops, b.delivered, b.Nodes()
```

Or hand it straight to the visualizer:

```python
cg.GenerateVisualizer(600, trace="bundle-trace.json")
```

## The format

```json
{
  "meta": {"run": "my-simulation"},
  "bundles": [
    {
      "id": "bundle-0001",
      "source": "dtn:mercury",
      "destination": "dtn:mars",
      "created_utc": "2026-06-01T00:00:00",
      "size_bytes": 1000000,
      "hops": [
        {
          "from": "dtn:mercury",
          "to": "dtn:venus",
          "tx_start_utc": "2026-06-01T00:00:00",
          "tx_stop_utc": "2026-06-01T00:02:58",
          "rx_utc": "2026-06-01T00:05:58",
          "owlt_s": 180.4,
          "status": "forwarded"
        }
      ]
    }
  ]
}
```

Only `id` and `hops` are required on a bundle, and only `to` and
`tx_start_utc` on a hop. Everything else is optional and either filled in or
left blank.

### Bundle fields

| Field | Notes |
|---|---|
| `id` | **required**, unique within the file |
| `hops` | **required**, may be empty |
| `source`, `destination` | inferred from the first and last hop if omitted |
| `created_utc` | |
| `size_bytes` | |
| `delivered` | inferred from a hop with status `delivered` if omitted |

### Hop fields

| Field | Notes |
|---|---|
| `to` | **required**, the receiving node |
| `tx_start_utc` | **required**, when transmission began |
| `from` | the sending node |
| `tx_stop_utc` | defaults to `tx_start_utc` |
| `rx_utc` | defaults to `tx_stop_utc` plus `owlt_s` |
| `owlt_s` | one-way light time, seconds |
| `status` | `forwarded`, `delivered`, `dropped`, `queued`, `expired` |

Endpoint identifiers should match the ones in your contact plan — `dtn:mars` by
default, or whatever you passed as `eid`. See {doc}`celestials`.
