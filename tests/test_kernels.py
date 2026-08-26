from __future__ import annotations

import pytest

from pycg_dtn import resolve
from pycg_dtn.kernels import (
    LSK,
    PCK,
    PLANETS,
    PLANETS_PROVIDES,
    SYSTEM_SPK,
    Kernel,
    required_for,
)


def names_for(*bodies: str) -> list[str]:
    return [k.filename for k in required_for([resolve(b) for b in bodies])]


def test_always_includes_the_three_base_kernels():
    got = names_for("Earth", "Venus")
    assert got[:3] == [LSK.filename, PCK.filename, PLANETS.filename]


def test_base_kernels_lead_even_when_satellites_are_added():
    got = names_for("Earth", "Mars")
    assert got[:3] == [LSK.filename, PCK.filename, PLANETS.filename]
    assert "mar099s.bsp" in got


def test_inner_planets_need_no_satellite_ephemeris():
    got = names_for("Sun", "Mercury", "Venus", "Earth")
    assert got == [LSK.filename, PCK.filename, PLANETS.filename]


@pytest.mark.parametrize(
    ("planet", "spk"),
    [
        ("Mars", "mar099s.bsp"),
        ("Jupiter", "jup365.bsp"),
        ("Saturn", "sat441.bsp"),
        ("Uranus", "ura116xl.bsp"),
        ("Neptune", "nep097.bsp"),
        ("Pluto", "plu060.bsp"),
    ],
)
def test_outer_planet_centres_need_their_satellite_ephemeris(planet, spk):
    assert spk in names_for("Earth", planet)


def test_earths_moon_comes_from_the_planetary_kernel():
    assert names_for("Earth", "Moon") == [
        LSK.filename,
        PCK.filename,
        PLANETS.filename,
    ]


def test_a_moon_pulls_in_its_systems_ephemeris():
    got = names_for("Earth", "Phobos")
    assert "mar099s.bsp" in got


def test_only_the_needed_systems_are_pulled_in():
    got = names_for("Earth", "Phobos")
    assert "jup365.bsp" not in got, "a Mars scenario must not pay for the 1 GB Jovian SPK"


def test_several_systems_are_all_included_and_deduped():
    got = names_for("Earth", "Phobos", "Deimos", "Io", "Callisto", "Titan")
    assert got.count("mar099s.bsp") == 1
    assert got.count("jup365.bsp") == 1
    assert "sat441.bsp" in got


def test_every_registered_system_kernel_has_a_plausible_url():
    for system, kernel in SYSTEM_SPK.items():
        assert isinstance(kernel, Kernel)
        assert kernel.url.startswith("https://naif.jpl.nasa.gov/")
        assert kernel.filename.endswith(".bsp")
        assert kernel.approx_mb > 0, f"system {system} has no recorded size"


@pytest.mark.parametrize("body", ["Sun", "Earth"])
def test_sun_and_inner_planets_need_no_satellite_kernel(body):
    assert names_for(body, "Venus") == [LSK.filename, PCK.filename, PLANETS.filename]


def test_everything_de440_provides_is_covered_without_satellite_kernels():
    bodies = [resolve(str(i)) for i in sorted(PLANETS_PROVIDES)]
    assert [k.filename for k in required_for(bodies)] == [
        LSK.filename,
        PCK.filename,
        PLANETS.filename,
    ]


@pytest.mark.network
def test_registry_matches_what_the_fetched_kernels_actually_contain(tmp_path):
    import spiceypy as sp

    from pycg_dtn.kernels import download

    bodies = [resolve(n) for n in ("Sun", "Mercury", "Venus", "Earth", "Moon")]
    required = required_for(bodies)
    assert [k.filename for k in required] == [
        LSK.filename,
        PCK.filename,
        PLANETS.filename,
    ]

    download(PLANETS, tmp_path, progress=False)
    covered = {int(i) for i in sp.spkobj(str(tmp_path / PLANETS.filename))}
    assert PLANETS_PROVIDES <= covered, "DE440 no longer provides what we assume"
    assert 499 not in covered, "DE440 unexpectedly gained the Mars centre"
