from __future__ import annotations

import pytest

from pycg_dtn import (
    ContactGraph,
    ContactGraphError,
    GeometryConfig,
    LinkBudget,
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


def test_add_satellite_is_not_implemented_yet():
    cg = ContactGraph()
    with pytest.raises(NotImplementedError, match="not implemented yet"):
        cg.AddSatellite(a=7000.0, e=0.001)


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
    with pytest.raises(ContactGraphError, match="at least one celestial"):
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
