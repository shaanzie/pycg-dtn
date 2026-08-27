from __future__ import annotations

import json

import pytest

from pycg_dtn import BundleTraceError
from pycg_dtn.bundletrace import load, loads

MINIMAL = {
    "bundles": [
        {
            "id": "b1",
            "hops": [
                {"from": "dtn:earth", "to": "dtn:mars",
                 "tx_start_utc": "2026-01-01T00:00:00"},
            ],
        }
    ]
}


def test_minimal_trace_parses():
    tr = loads(json.dumps(MINIMAL))
    assert len(tr) == 1
    assert tr.bundles[0].id == "b1"
    assert tr.bundles[0].n_hops == 1


def test_source_and_destination_are_inferred_from_hops():
    b = loads(json.dumps(MINIMAL)).Get("b1")
    assert b.source == "dtn:earth"
    assert b.destination == "dtn:mars"


def test_explicit_source_and_destination_win():
    raw = json.loads(json.dumps(MINIMAL))
    raw["bundles"][0]["source"] = "dtn:sun"
    raw["bundles"][0]["destination"] = "dtn:pluto"
    b = loads(json.dumps(raw)).Get("b1")
    assert b.source == "dtn:sun"
    assert b.destination == "dtn:pluto"


def test_delivered_is_inferred_from_hop_status():
    raw = json.loads(json.dumps(MINIMAL))
    assert loads(json.dumps(raw)).Get("b1").delivered is False
    raw["bundles"][0]["hops"][0]["status"] = "delivered"
    assert loads(json.dumps(raw)).Get("b1").delivered is True


def test_from_is_exposed_as_sender():
    hop = loads(json.dumps(MINIMAL)).Get("b1").hops[0]
    assert hop.sender == "dtn:earth"
    assert hop.to == "dtn:mars"


def test_nodes_lists_the_path_in_order():
    raw = {
        "bundles": [
            {
                "id": "b",
                "hops": [
                    {"from": "a", "to": "b", "tx_start_utc": "t"},
                    {"from": "b", "to": "c", "tx_start_utc": "t"},
                ],
            }
        ]
    }
    assert loads(json.dumps(raw)).Get("b").Nodes() == ["a", "b", "c"]


def test_round_trips_through_as_dict():
    tr = loads(json.dumps(MINIMAL))
    again = loads(json.dumps(tr.AsDict()))
    assert again.Get("b1").hops[0].sender == "dtn:earth"


def test_terminal_statuses():
    raw = json.loads(json.dumps(MINIMAL))
    for status, terminal in [
        ("forwarded", False), ("queued", False),
        ("delivered", True), ("dropped", True), ("expired", True),
    ]:
        raw["bundles"][0]["hops"][0]["status"] = status
        assert loads(json.dumps(raw)).Get("b1").hops[0].is_terminal is terminal


def test_unknown_bundle_id_raises():
    with pytest.raises(BundleTraceError, match="no bundle"):
        loads(json.dumps(MINIMAL)).Get("nope")


def test_invalid_json_raises():
    with pytest.raises(BundleTraceError, match="not valid JSON"):
        loads("{not json")


def test_missing_bundles_list_raises():
    with pytest.raises(BundleTraceError, match="'bundles' list"):
        loads(json.dumps({"meta": {}}))


def test_bundle_without_id_raises():
    with pytest.raises(BundleTraceError, match="'id'"):
        loads(json.dumps({"bundles": [{"hops": []}]}))


def test_hop_without_destination_raises():
    raw = {"bundles": [{"id": "b", "hops": [{"tx_start_utc": "t"}]}]}
    with pytest.raises(BundleTraceError, match="'to'"):
        loads(json.dumps(raw))


def test_hop_without_start_time_raises():
    raw = {"bundles": [{"id": "b", "hops": [{"to": "x"}]}]}
    with pytest.raises(BundleTraceError, match="tx_start_utc"):
        loads(json.dumps(raw))


def test_non_numeric_owlt_raises():
    raw = json.loads(json.dumps(MINIMAL))
    raw["bundles"][0]["hops"][0]["owlt_s"] = "soon"
    with pytest.raises(BundleTraceError, match="owlt_s"):
        loads(json.dumps(raw))


def test_hops_must_be_a_list():
    with pytest.raises(BundleTraceError, match="'hops' must be a list"):
        loads(json.dumps({"bundles": [{"id": "b", "hops": {}}]}))


def test_missing_file_raises(tmp_path):
    with pytest.raises(BundleTraceError, match="no bundle trace at"):
        load(tmp_path / "absent.json")


def test_load_reads_a_file(tmp_path):
    p = tmp_path / "bundle-trace.json"
    p.write_text(json.dumps(MINIMAL))
    assert load(p).Get("b1").n_hops == 1
