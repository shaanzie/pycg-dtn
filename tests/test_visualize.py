from __future__ import annotations

import json
import re

import numpy as np
import pytest

from pycg_dtn import ContactGraph, VisualizerError
from pycg_dtn.visualize import (
    BODY_COLORS,
    MAX_STEPS,
    SATELLITE_COLOR,
    _step_times,
    body_color,
)


def payload_of(html: str) -> dict:
    m = re.search(r"const DATA = (\{.*?\});\n", html, re.S)
    assert m, "no payload embedded in the page"
    return json.loads(m.group(1))


def test_step_times_span_the_plan():
    t = _step_times(0.0, 3600.0 * 5, 3600.0)
    assert len(t) == 6
    assert t[0] == 0.0 and t[-1] == 3600.0 * 5


def test_step_size_must_be_positive():
    with pytest.raises(VisualizerError, match="must be positive"):
        _step_times(0.0, 100.0, 0.0)


def test_step_size_larger_than_the_span_is_rejected():
    with pytest.raises(VisualizerError, match="longer than"):
        _step_times(0.0, 100.0, 1000.0)


def test_too_many_steps_is_rejected_with_a_usable_suggestion():
    with pytest.raises(VisualizerError, match=f"limit {MAX_STEPS:,}"):
        _step_times(0.0, 86400.0 * 400, 60.0)


def test_celestials_get_their_own_colour_and_satellites_grey():
    cg = ContactGraph()
    earth = cg.AddCelestial("Earth")
    sat = cg.AddSatellite("RELAY", "Mars", semi_major_axis_km=3800.0)
    assert body_color(earth) == BODY_COLORS["EARTH"]
    assert body_color(sat) == SATELLITE_COLOR


@pytest.mark.network
def test_generates_a_self_contained_page(mars_kernels, tmp_path):
    cg = ContactGraph(kernel_dir=mars_kernels)
    cg.AddCelestial("Earth")
    cg.AddCelestial("Mars")
    cg.AddSatellite("RELAY", "Mars", altitude_km=400, inclination_deg=93.0)
    cg.GenerateContactGraph(days=1, start="2026-06-01T00:00:00", progress=False)

    out = cg.GenerateVisualizer(3600, out=tmp_path / "v.html")
    html = out.read_text()

    # nothing may be fetched at view time
    assert "http://" not in html
    assert "https://" not in html
    assert "<script src" not in html


@pytest.mark.network
def test_payload_frames_and_stepping(mars_kernels, tmp_path):
    cg = ContactGraph(kernel_dir=mars_kernels)
    cg.AddCelestial("Earth")
    cg.AddCelestial("Mars")
    cg.AddSatellite("RELAY", "Mars", altitude_km=400, inclination_deg=93.0)
    cg.GenerateContactGraph(days=1, start="2026-06-01T00:00:00", progress=False)

    data = payload_of(cg.GenerateVisualizer(3600, out=tmp_path / "v.html").read_text())

    assert data["meta"]["n_steps"] == 25
    assert data["meta"]["step_size_s"] == 3600.0

    bodies = {b["name"]: b for b in data["bodies"]}
    # a satellite is stored relative to its central body, keeping its offset
    # from being lost against a heliocentric magnitude
    assert bodies["RELAY"]["central"] == "MARS"
    assert np.linalg.norm(bodies["RELAY"]["pos"][0]) == pytest.approx(3796, rel=0.05)
    assert bodies["MARS"]["central"] is None
    assert np.linalg.norm(bodies["MARS"]["pos"][0]) > 1e8

    assert "SUN" in bodies
    assert bodies["SUN"]["node"] is False
    assert bodies["EARTH"]["node"] is True

    for b in data["bodies"]:
        assert len(b["pos"]) == data["meta"]["n_steps"]


@pytest.mark.network
def test_central_body_is_included_even_when_not_a_node(mars_kernels, tmp_path):
    cg = ContactGraph(kernel_dir=mars_kernels)
    cg.AddCelestial("Earth")
    cg.AddSatellite("RELAY", "Mars", altitude_km=400)
    cg.GenerateContactGraph(days=1, start="2026-06-01T00:00:00", progress=False)

    data = payload_of(cg.GenerateVisualizer(3600, out=tmp_path / "v.html").read_text())
    bodies = {b["name"]: b for b in data["bodies"]}
    assert "MARS" in bodies, "the satellite cannot be placed without its centre"
    assert bodies["MARS"]["node"] is False


@pytest.mark.network
def test_orbiter_is_occulted_across_the_steps(mars_kernels, tmp_path):
    cg = ContactGraph(kernel_dir=mars_kernels)
    cg.AddCelestial("Earth")
    cg.AddCelestial("Mars")
    cg.AddSatellite("RELAY", "Mars", altitude_km=400, inclination_deg=93.0)
    cg.GenerateContactGraph(days=1, start="2026-06-01T00:00:00", progress=False)

    data = payload_of(cg.GenerateVisualizer(1800, out=tmp_path / "v.html").read_text())
    links = [(link["a"], link["b"]) for link in data["links"]]
    i = links.index(("EARTH", "RELAY"))

    seen = [i in step for step in data["active"]]
    assert any(seen) and not all(seen), "Mars should hide its orbiter part of the time"


@pytest.mark.network
def test_trace_is_embedded_when_supplied(mars_kernels, tmp_path):
    trace = tmp_path / "bundle-trace.json"
    trace.write_text(json.dumps({
        "bundles": [{
            "id": "b1",
            "hops": [{"from": "dtn:earth", "to": "dtn:mars",
                      "tx_start_utc": "2026-06-01T00:00:00", "owlt_s": 600.0,
                      "status": "delivered"}],
        }]
    }))

    cg = ContactGraph(kernel_dir=mars_kernels)
    cg.AddCelestial("Earth")
    cg.AddCelestial("Mars")
    cg.GenerateContactGraph(days=1, start="2026-06-01T00:00:00", progress=False)

    out = cg.GenerateVisualizer(3600, out=tmp_path / "v.html", trace=trace)
    data = payload_of(out.read_text())
    assert data["trace"]["bundles"][0]["id"] == "b1"


@pytest.mark.network
def test_without_a_trace_the_tab_is_empty_not_broken(mars_kernels, tmp_path):
    cg = ContactGraph(kernel_dir=mars_kernels)
    cg.AddCelestial("Earth")
    cg.AddCelestial("Mars")
    cg.GenerateContactGraph(days=1, start="2026-06-01T00:00:00", progress=False)

    data = payload_of(
        cg.GenerateVisualizer(3600, out=tmp_path / "v.html").read_text()
    )
    assert data["trace"] is None


def test_visualizer_without_a_plan_explains_itself():
    cg = ContactGraph()
    cg.AddCelestial("Earth")
    cg.AddCelestial("Mars")
    with pytest.raises(Exception, match="GenerateContactGraph"):
        cg.GenerateVisualizer(3600)


@pytest.mark.network
def test_a_moon_orbits_its_planet_not_the_sun(mars_kernels, tmp_path):
    cg = ContactGraph(kernel_dir=mars_kernels)
    cg.AddCelestial("Mars")
    cg.AddCelestial("Phobos")
    cg.GenerateContactGraph(days=1, start="2026-06-01T00:00:00", progress=False)

    data = payload_of(cg.GenerateVisualizer(3600, out=tmp_path / "v.html").read_text())
    phobos = {b["name"]: b for b in data["bodies"]}["PHOBOS"]

    assert phobos["central"] == "MARS"
    # Phobos orbits 9,376 km from Mars, not 1.5 astronomical units from the Sun
    radii = [np.linalg.norm(p) for p in phobos["orbit"]]
    assert 9_000 < min(radii) and max(radii) < 10_000


@pytest.mark.network
def test_the_sun_is_drawn_without_an_orbit_of_its_own(mars_kernels, tmp_path):
    cg = ContactGraph(kernel_dir=mars_kernels)
    cg.AddCelestial("Sun")
    cg.AddCelestial("Mars")
    cg.GenerateContactGraph(days=1, start="2026-06-01T00:00:00", progress=False)

    data = payload_of(cg.GenerateVisualizer(3600, out=tmp_path / "v.html").read_text())
    sun = {b["name"]: b for b in data["bodies"]}["SUN"]

    assert sun["orbit"] == [], "the Sun does not orbit itself"
    assert sun["central"] is None


@pytest.mark.network
def test_an_orbit_longer_than_the_plan_is_still_drawn_whole(mars_kernels, tmp_path):
    # One revolution takes about 291 days, far past the one-day plan; the
    # scratch ephemeris has to stretch to cover it
    cg = ContactGraph(kernel_dir=mars_kernels)
    cg.AddCelestial("Mars")
    cg.AddSatellite("HELIO", "Sun", semi_major_axis_km=128_654_169.0,
                    inclination_deg=23.44)
    cg.GenerateContactGraph(days=1, start="2026-06-01T00:00:00", progress=False)

    data = payload_of(cg.GenerateVisualizer(3600, out=tmp_path / "v.html").read_text())
    helio = {b["name"]: b for b in data["bodies"]}["HELIO"]

    assert len(helio["orbit"]) > 2
    # A closed revolution comes back to where it started
    first, last = np.array(helio["orbit"][0]), np.array(helio["orbit"][-1])
    assert np.linalg.norm(first - last) < 0.02 * np.linalg.norm(first)
