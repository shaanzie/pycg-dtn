from __future__ import annotations

import math

import pytest
import spiceypy as sp

from pycg_dtn import KeplerianElements, SatelliteError
from pycg_dtn.celestials import resolve
from pycg_dtn.satellites import Satellite, synthetic_id

MARS_RADIUS_KM = 3396.19
MARS_GM = 42828.37


def elements(**kw) -> KeplerianElements:
    base = dict(central="MARS", semi_major_axis_km=3800.0)
    base.update(kw)
    return KeplerianElements(**base)


def test_periapsis_and_apoapsis_follow_from_eccentricity():
    e = elements(semi_major_axis_km=10000.0, eccentricity=0.2)
    assert e.periapsis_km == pytest.approx(8000.0)
    assert e.apoapsis_km == pytest.approx(12000.0)


def test_circular_orbit_has_equal_apsides():
    e = elements(semi_major_axis_km=3800.0)
    assert e.periapsis_km == e.apoapsis_km == 3800.0


def test_rejects_nonpositive_semi_major_axis():
    with pytest.raises(SatelliteError, match="must be positive"):
        elements(semi_major_axis_km=0.0)
    with pytest.raises(SatelliteError, match="must be positive"):
        elements(semi_major_axis_km=-100.0)


def test_rejects_open_orbits():
    with pytest.raises(SatelliteError, match=r"\[0, 1\)"):
        elements(eccentricity=1.0)
    with pytest.raises(SatelliteError, match=r"\[0, 1\)"):
        elements(eccentricity=1.5)


def test_rejects_out_of_range_inclination():
    with pytest.raises(SatelliteError, match="inclination"):
        elements(inclination_deg=181.0)
    with pytest.raises(SatelliteError, match="inclination"):
        elements(inclination_deg=-1.0)


def test_unknown_central_body_rejected():
    with pytest.raises(SatelliteError, match="unknown central body"):
        KeplerianElements(central="Tatooine", semi_major_axis_km=3800.0).CentralBody()


def test_conic_array_is_what_spice_expects():
    e = elements(
        semi_major_axis_km=10000.0,
        eccentricity=0.1,
        inclination_deg=90.0,
        raan_deg=45.0,
        arg_periapsis_deg=30.0,
        mean_anomaly_deg=180.0,
    )
    arr = e.AsConicArray(epoch_et=0.0, mu=MARS_GM)
    assert len(arr) == 8
    assert arr[0] == pytest.approx(9000.0)        
    assert arr[1] == pytest.approx(0.1)
    assert arr[2] == pytest.approx(math.pi / 2)   
    assert arr[3] == pytest.approx(math.radians(45.0))
    assert arr[6] == 0.0
    assert arr[7] == MARS_GM


def test_synthetic_ids_are_negative_and_distinct():
    ids = [synthetic_id(i) for i in range(5)]
    assert len(set(ids)) == 5
    assert all(i < 0 for i in ids)


def test_satellite_defaults_its_eid_from_the_name():
    sat = Satellite(
        name="MARS RELAY 1",
        naif_id=synthetic_id(0),
        central=resolve("Mars"),
        elements=elements(),
    )
    assert sat.eid == "dtn:mars-relay-1"


def test_satellite_eid_can_be_overridden():
    sat = Satellite(
        name="RELAY",
        naif_id=synthetic_id(0),
        central=resolve("Mars"),
        elements=elements(),
        eid="ipn:9.1",
    )
    assert sat.eid == "ipn:9.1"


@pytest.mark.network
def test_period_matches_keplers_third_law(mars_kernels):
    # a = 3800 km about Mars is about 118 minutes
    e = elements(semi_major_axis_km=3800.0)
    mu = e.GravitationalParameter()
    expected = 2.0 * math.pi * math.sqrt(3800.0**3 / mu)
    assert e.PeriodSeconds() == pytest.approx(expected)
    assert 115 * 60 < e.PeriodSeconds() < 122 * 60


@pytest.mark.network
def test_orbit_inside_the_central_body_is_rejected(mars_kernels):
    e = elements(semi_major_axis_km=MARS_RADIUS_KM - 100.0)
    with pytest.raises(SatelliteError, match="intersects the surface"):
        e.CheckClearsSurface()


@pytest.mark.network
def test_gm_lookup_needs_the_gm_kernel(mars_kernels):
    assert elements().GravitationalParameter() == pytest.approx(MARS_GM, rel=1e-4)


@pytest.mark.network
def test_propagated_spk_reproduces_the_elements(mars_kernels, tmp_path):
    import numpy as np

    from pycg_dtn.propagate import write_spk

    sat = Satellite(
        name="PYCG_TEST_SAT",
        naif_id=synthetic_id(99),
        central=resolve("Mars"),
        elements=elements(eccentricity=0.001, inclination_deg=93.0),
    )
    t0 = sp.str2et("2026-01-01T00:00:00")
    t1 = t0 + 2 * 86400.0
    path = write_spk(sat, t0, t1, tmp_path / "sat.bsp")

    assert path.is_file()
    assert sat.naif_id in [int(i) for i in sp.spkobj(str(path))]

    sp.furnsh(str(path))
    try:
        conic = sat.elements.AsConicArray(
            sp.str2et(sat.elements.epoch_utc), sat.elements.GravitationalParameter()
        )
        for dt in (0.0, 600.0, 3600.0, 7200.0):
            truth = sp.conics(conic, t0 + dt)[:3]
            got, _ = sp.spkpos(str(sat.naif_id), t0 + dt, "J2000", "NONE", "MARS")
            assert np.linalg.norm(truth - np.asarray(got)) < 1e-6
    finally:
        sp.unload(str(path))


@pytest.mark.network
def test_spk_covers_beyond_the_span_for_light_time_lookback(mars_kernels, tmp_path):
    from pycg_dtn.propagate import COVERAGE_PAD_S, write_spk

    sat = Satellite(
        name="PYCG_PAD_SAT",
        naif_id=synthetic_id(98),
        central=resolve("Mars"),
        elements=elements(),
    )
    t0 = sp.str2et("2026-01-01T00:00:00")
    t1 = t0 + 86400.0
    path = write_spk(sat, t0, t1, tmp_path / "pad.bsp")

    cover = sp.cell_double(2000)
    sp.spkcov(str(path), sat.naif_id, cover)
    start, stop = sp.wnfetd(cover, 0)
    assert start <= t0 - COVERAGE_PAD_S + 1.0
    assert stop >= t1 + COVERAGE_PAD_S - 1.0
