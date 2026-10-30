from __future__ import annotations

import math

import numpy as np
import pytest
import spiceypy as sp

from pycg_dtn import ContactGraph, GroundStationError, LinkBudget, SatelliteError
from pycg_dtn import geometry as geo
from pycg_dtn.celestials import resolve
from pycg_dtn.propagate import SatelliteEphemerides
from pycg_dtn.stations import GroundStation, station_id


def _station(**kwargs) -> GroundStation:
    args = {
        "name": "SITE",
        "naif_id": station_id(0),
        "central": resolve("Earth"),
        "latitude_deg": 10.0,
        "longitude_deg": 20.0,
    }
    args.update(kwargs)
    return GroundStation(**args)


def test_rejects_latitude_out_of_range():
    with pytest.raises(GroundStationError, match="latitude_deg"):
        _station(latitude_deg=91.0)


def test_rejects_elevation_mask_out_of_range():
    with pytest.raises(GroundStationError, match="min_elevation_deg"):
        _station(min_elevation_deg=90.0)


def test_station_defaults_its_eid_from_the_name():
    assert _station(name="DSS 14").eid == "dtn:dss-14"


def test_station_ids_do_not_collide_with_satellite_ids():
    from pycg_dtn.satellites import synthetic_id

    assert station_id(0) != synthetic_id(0)
    assert station_id(0) < 0


def test_add_ground_station_becomes_a_node_in_its_body_domain():
    cg = ContactGraph()
    cg.AddCelestial("Moon")
    gs = cg.AddGroundStation(
        "Goldstone", "Earth", latitude_deg=35.4, longitude_deg=-116.9
    )
    assert gs.name == "GOLDSTONE"
    assert gs.is_station and gs.is_artificial
    assert gs.domain == "earth"
    assert cg.GetStations() == [gs]
    assert [n.name for n in cg.GetNodes()] == ["MOON", "GOLDSTONE"]


def test_station_name_cannot_clash_with_a_satellite():
    cg = ContactGraph()
    cg.AddSatellite("RELAY", "Mars", semi_major_axis_km=3800.0)
    with pytest.raises(SatelliteError, match="already in the graph"):
        cg.AddGroundStation("relay", "Earth", latitude_deg=0.0, longitude_deg=0.0)


def test_stations_on_the_same_body_are_not_linked():
    cg = ContactGraph()
    cg.AddGroundStation("A", "Earth", latitude_deg=35.0, longitude_deg=-117.0)
    cg.AddGroundStation("B", "Earth", latitude_deg=40.0, longitude_deg=-4.0)
    cg.AddGroundStation("C", "Moon", latitude_deg=-89.5, longitude_deg=0.0)
    pairs = [{a.name, b.name} for a, b in cg.GetLinks()]
    assert {"A", "B"} not in pairs
    assert {"A", "C"} in pairs and {"B", "C"} in pairs


def test_station_on_mars_needs_the_mars_system_kernel():
    cg = ContactGraph()
    cg.AddGroundStation("JEZERO", "Mars", latitude_deg=18.4, longitude_deg=77.5)
    names = [k.filename for k in cg.RequiredKernels()]
    assert "mar099s.bsp" in names


@pytest.mark.network
def test_body_fixed_position_on_the_equator(mars_kernels):
    radius = float(sp.bodvrd("EARTH", "RADII", 3)[1][0])
    pos = _station(latitude_deg=0.0, longitude_deg=0.0).BodyFixedPosition()
    assert pos == pytest.approx([radius, 0.0, 0.0], abs=1e-6)


@pytest.mark.network
def test_station_spk_is_fixed_in_the_body_frame(mars_kernels):
    station = _station(latitude_deg=35.0, longitude_deg=-117.0)
    t0 = sp.str2et("2026-01-01T00:00:00")
    eph = SatelliteEphemerides([], [station])
    eph.Build(t0, t0 + 86400.0)
    try:
        fixed = []
        inertial = []
        for et in (t0, t0 + 6 * 3600.0):
            fixed.append(sp.spkpos(station.name, et, "IAU_EARTH", "NONE", "EARTH")[0])
            inertial.append(sp.spkpos(station.name, et, "J2000", "NONE", "EARTH")[0])
        assert fixed[0] == pytest.approx(station.BodyFixedPosition(), abs=1e-6)
        assert fixed[1] == pytest.approx(fixed[0], abs=1e-6)
        # A quarter day later Earth has turned about 90 degrees
        cos_turn = np.dot(inertial[0], inertial[1]) / np.dot(inertial[0], inertial[0])
        assert math.degrees(math.acos(cos_turn)) > 45.0
    finally:
        eph.Cleanup()


@pytest.mark.network
def test_moon_elevation_from_the_north_pole_is_its_declination(mars_kernels):
    station = _station(latitude_deg=90.0, longitude_deg=0.0)
    et = sp.str2et("2026-03-01T00:00:00")
    eph = SatelliteEphemerides([], [station])
    eph.Build(et, et + 3600.0)
    try:
        moon = sp.spkpos("MOON", et, "J2000", "NONE", "EARTH")[0]
        declination = math.degrees(math.asin(moon[2] / np.linalg.norm(moon)))
        # Parallax (about 1 deg) and pole precession keep this from being exact
        elevation = geo.elevation_deg(station, "MOON", et)
        assert elevation == pytest.approx(declination, abs=1.5)
    finally:
        eph.Cleanup()


@pytest.mark.network
def test_contacts_follow_the_elevation_mask(mars_kernels):
    cg = ContactGraph(kernel_dir=mars_kernels)
    cg.AddCelestial("Moon")
    cg.AddGroundStation(
        "GDS", "Earth", latitude_deg=35.4, longitude_deg=-116.9, min_elevation_deg=10.0
    )
    plan = cg.GenerateContactGraph(days=2, start="2026-11-01T00:00:00", progress=False)
    summary = plan.summary[0]
    # Earth hides the Moon from the site for part of each day, but is not a blocker
    assert "EARTH" not in summary.blockers
    assert 0.2 < summary.contact_fraction < 0.8
    assert summary.n_outages >= 1


@pytest.mark.network
def test_asymmetric_budgets_give_each_direction_its_own_rate(mars_kernels):
    cg = ContactGraph(kernel_dir=mars_kernels)
    cg.AddCelestial("Moon", group="moon")
    cg.AddGroundStation(
        "GDS", "Earth", latitude_deg=35.4, longitude_deg=-116.9, group="ground"
    )
    cg.SetLinkBudgetFor("ground", "moon", LinkBudget(tx_power_w=1000.0))
    cg.SetLinkBudgetFor("moon", "ground", LinkBudget(tx_power_w=10.0))
    plan = cg.GenerateContactGraph(days=1, start="2026-11-01T00:00:00", progress=False)
    contact = plan.contacts[0]
    # Contact a -> b is MOON -> GDS (node order); the uplink is the faster way
    assert contact.a == "MOON"
    assert contact.reverse_rate_bps > contact.rate_bps
