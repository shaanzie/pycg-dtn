from __future__ import annotations

import pytest

from pycg_dtn import (
    ContactGraph,
    ContactGraphError,
    GeometryConfig,
    LinkBudget,
    SatelliteError,
    UnknownCelestialBodyError,
)


def test_add_celestial_returns_the_resolved_body():
    cg = ContactGraph()
    mars = cg.AddCelestial("Mars")
    assert mars.name == "MARS"
    assert mars.naif_id == 499
    assert cg.GetCelestials() == [mars]


def test_add_celestial_rejects_unknown_body():
    cg = ContactGraph()
    with pytest.raises(UnknownCelestialBodyError, match="no ID code"):
        cg.AddCelestial("Tatooine")


def test_add_celestial_rejects_duplicates_including_aliases():
    cg = ContactGraph()
    cg.AddCelestial("Mars")
    with pytest.raises(UnknownCelestialBodyError, match="already in the graph"):
        cg.AddCelestial("mars")
    with pytest.raises(UnknownCelestialBodyError, match="already in the graph"):
        cg.AddCelestial("499")


def test_custom_eid_is_kept():
    cg = ContactGraph()
    body = cg.AddCelestial("Mars", eid="ipn:4.1")
    assert body.eid == "ipn:4.1"


def test_links_are_every_unordered_pair():
    cg = ContactGraph()
    for name in ("Earth", "Mars", "Jupiter"):
        cg.AddCelestial(name)
    assert len(cg.GetLinks()) == 3


def test_link_kind_follows_planetary_system():
    cg = ContactGraph()
    mars = cg.AddCelestial("Mars")
    phobos = cg.AddCelestial("Phobos")
    earth = cg.AddCelestial("Earth")

    assert cg.LinkKind(mars, phobos) == "intra"
    assert cg.LinkKind(mars, earth) == "inter"


def test_add_satellite_becomes_a_node():
    cg = ContactGraph()
    cg.AddCelestial("Mars")
    sat = cg.AddSatellite("SURVEYOR", "Mars", semi_major_axis_km=3800.0)
    assert sat.name == "SURVEYOR"
    assert sat.eid == "dtn:surveyor"
    assert [n.name for n in cg.GetNodes()] == ["MARS", "SURVEYOR"]
    assert len(cg.GetLinks()) == 1


def test_satellite_shares_the_clock_domain_of_its_central_body():
    cg = ContactGraph()
    sat = cg.AddSatellite("AREO", "Mars", semi_major_axis_km=3800.0)
    assert sat.domain == "mars"
    assert sat.system == 4
    assert sat.is_artificial
    assert not sat.is_planet


def test_satellite_link_to_its_own_planet_is_intra_domain():
    cg = ContactGraph()
    mars = cg.AddCelestial("Mars")
    sat = cg.AddSatellite("AREO", "Mars", semi_major_axis_km=3800.0)
    assert cg.LinkKind(mars, sat) == "intra"
    assert cg.LinkKind(cg.AddCelestial("Earth"), sat) == "inter"


def test_satellite_needs_exactly_one_orbit_size():
    cg = ContactGraph()
    with pytest.raises(SatelliteError, match="exactly one"):
        cg.AddSatellite("X", "Mars")
    with pytest.raises(SatelliteError, match="exactly one"):
        cg.AddSatellite("X", "Mars", semi_major_axis_km=3800.0, altitude_km=400.0)


def test_duplicate_satellite_name_rejected():
    cg = ContactGraph()
    cg.AddSatellite("AREO", "Mars", semi_major_axis_km=3800.0)
    with pytest.raises(SatelliteError, match="already in the graph"):
        cg.AddSatellite("areo", "Mars", semi_major_axis_km=3900.0)


def test_satellites_get_distinct_naif_codes():
    cg = ContactGraph()
    a = cg.AddSatellite("A", "Mars", semi_major_axis_km=3800.0)
    b = cg.AddSatellite("B", "Mars", semi_major_axis_km=3900.0)
    assert a.naif_id != b.naif_id
    assert a.naif_id < 0 and b.naif_id < 0


def test_satellite_pulls_in_the_gm_kernel_and_its_central_body():
    cg = ContactGraph()
    cg.AddSatellite("AREO", "Mars", semi_major_axis_km=3800.0)
    names = [k.filename for k in cg.RequiredKernels()]
    assert "gm_de440.tpc" in names
    assert "mar099s.bsp" in names


def test_central_body_occults_its_orbiter_even_when_not_a_node():
    cg = ContactGraph()
    cg.AddCelestial("Earth")
    cg.AddSatellite("RELAY", "Mars", semi_major_axis_km=3800.0)

    nodes = cg.GetNodes()
    candidates = cg._OcculterCandidates(nodes)
    assert "MARS" in [b.name for b in candidates]
    assert [b.name for b in nodes] == ["EARTH", "RELAY"]


def test_occulter_candidates_do_not_duplicate_an_existing_node():
    cg = ContactGraph()
    cg.AddCelestial("Mars")
    cg.AddSatellite("RELAY", "Mars", semi_major_axis_km=3800.0)
    names = [b.name for b in cg._OcculterCandidates(cg.GetNodes())]
    assert names.count("MARS") == 1


def test_generate_needs_at_least_two_nodes():
    cg = ContactGraph()
    cg.AddCelestial("Earth")
    with pytest.raises(ContactGraphError, match="at least two nodes"):
        cg.GenerateContactGraph(days=10)


def test_generate_rejects_nonpositive_days():
    cg = ContactGraph()
    cg.AddCelestial("Earth")
    cg.AddCelestial("Mars")
    with pytest.raises(ValueError, match="days must be positive"):
        cg.GenerateContactGraph(days=0)


def test_required_kernels_needs_no_download(tmp_path):
    cg = ContactGraph(kernel_dir=tmp_path)
    cg.AddCelestial("Earth")
    cg.AddCelestial("Phobos")
    names = [k.filename for k in cg.RequiredKernels()]
    assert "mar099s.bsp" in names
    assert not list(tmp_path.iterdir()), "listing kernels must not download them"


def test_fetch_requires_a_body(tmp_path):
    cg = ContactGraph(kernel_dir=tmp_path)
    with pytest.raises(ContactGraphError, match="at least one body"):
        cg.FetchKernels()


def test_config_objects_are_mutable_in_place():
    cg = ContactGraph()
    cg.GetLinkBudget().SetFrequency(32.0e9)
    cg.GetGeometry().SetSepExclusion(2.0)

    assert cg.GetLinkBudget().GetFrequency() == 32.0e9
    assert cg.GetGeometry().GetSepExclusion() == 2.0


def test_set_config_rejects_wrong_type():
    cg = ContactGraph()
    with pytest.raises(TypeError):
        cg.SetLinkBudget(GeometryConfig())
    with pytest.raises(TypeError):
        cg.SetGeometry(LinkBudget())


def test_kernel_dir_setter():
    cg = ContactGraph()
    cg.SetKernelDir("/tmp/some-kernels")
    assert str(cg.GetKernelDir()) == "/tmp/some-kernels"
