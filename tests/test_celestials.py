from __future__ import annotations

import pytest

from pycg_dtn import UnknownCelestialBodyError, resolve


@pytest.mark.parametrize(
    ("name", "naif_id"),
    [
        ("Sun", 10),
        ("EARTH", 399),
        ("mars", 499),
        ("Phobos", 401),
        ("Io", 501),
        ("Callisto", 504),
        ("Titan", 606),
        ("Triton", 801),
        ("Charon", 901),
    ],
)
def test_resolve_is_case_insensitive(name, naif_id):
    assert resolve(name).naif_id == naif_id


def test_resolve_canonicalises_name():
    assert resolve("mars").name == "MARS"


def test_resolve_accepts_integer_code_as_string():
    body = resolve("401")
    assert body.name == "PHOBOS"
    assert body.naif_id == 401


def test_unknown_name_raises():
    with pytest.raises(UnknownCelestialBodyError, match="no ID code"):
        resolve("Vulcan")


def test_empty_name_raises():
    with pytest.raises(UnknownCelestialBodyError):
        resolve("   ")


def test_system_and_domain_group_by_planetary_system():
    mars, phobos, deimos = resolve("Mars"), resolve("Phobos"), resolve("Deimos")
    assert mars.system == phobos.system == deimos.system == 4
    assert mars.domain == phobos.domain == "mars"

    assert resolve("Io").domain == resolve("Jupiter").domain == "jupiter"
    assert resolve("Io").domain != mars.domain


def test_sun_belongs_to_no_planetary_system():
    sun = resolve("Sun")
    assert sun.system == 0
    assert sun.domain == "sun"


def test_is_planet_only_true_for_n99_codes():
    assert resolve("Mars").is_planet
    assert resolve("Jupiter").is_planet
    assert not resolve("Phobos").is_planet
    assert not resolve("Sun").is_planet


def test_default_eid_and_override():
    assert resolve("Mars").eid == "dtn:mars"
    assert resolve("Mars", eid="ipn:4.1").eid == "ipn:4.1"
