from __future__ import annotations

from pycg_dtn.orbital_id import (
    BP_VERSION,
    REGIME_BODY,
    REGIME_SATELLITE,
    SCHEME,
    SCHEME_VERSION,
    BuildEid,
)


def test_body_eid_has_no_state_suffix():
    eid = BuildEid("mars", REGIME_BODY, "MARS")
    assert eid == f"{SCHEME}://{BP_VERSION}::{SCHEME_VERSION}::mars::body::mars"


def test_satellite_eid_appends_orbital_state():
    elements = {
        "epoch_utc": "2026-01-01T00:00:00",
        "semi_major_axis_km": 3800.0,
        "eccentricity": 0.01,
        "inclination_deg": 93.0,
        "raan_deg": 10.0,
        "arg_periapsis_deg": 20.0,
        "mean_anomaly_deg": 30.0,
    }
    eid = BuildEid("mars", REGIME_SATELLITE, "MRO", elements=elements)
    assert eid == (
        "oip://bp7::v1::mars::sat::mro::"
        "2026-01-01T00:00:00::3800.000::0.010000::93.000000::10.000000::"
        "20.000000::30.000000"
    )


def test_domain_and_node_id_are_slugified():
    eid = BuildEid("Mars System", REGIME_BODY, "Mars Relay 1")
    assert eid == "oip://bp7::v1::mars-system::body::mars-relay-1"


def test_scope_prefix_is_a_truncatable_head_of_the_full_eid():
    scope_only = BuildEid("mars", REGIME_SATELLITE, "MRO")
    full = BuildEid(
        "mars",
        REGIME_SATELLITE,
        "MRO",
        elements={
            "epoch_utc": "2026-01-01T00:00:00",
            "semi_major_axis_km": 3800.0,
            "eccentricity": 0.0,
            "inclination_deg": 0.0,
            "raan_deg": 0.0,
            "arg_periapsis_deg": 0.0,
            "mean_anomaly_deg": 0.0,
        },
    )
    assert full.startswith(scope_only + "::")
