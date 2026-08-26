from __future__ import annotations

import math

import numpy as np
import pytest

from pycg_dtn import GeometryConfig
from pycg_dtn.geometry import AU_KM, segment_distances


def test_defaults_round_trip():
    g = GeometryConfig()
    assert g.GetOccultStep() == 600.0
    assert g.GetCoronaStep() == 6 * 3600.0
    assert g.GetSepExclusion() == 3.0
    assert g.GetRateTolerance() == 0.10


def test_setters_chain_and_take_effect():
    g = GeometryConfig().SetOccultStep(300.0).SetSepExclusion(1.5)
    assert g.GetOccultStep() == 300.0
    assert g.GetSepExclusion() == 1.5


@pytest.mark.parametrize(
    "setter", ["SetOccultStep", "SetCoronaStep", "SetSepExclusion", "SetRateTolerance"]
)
def test_nonpositive_values_rejected(setter):
    g = GeometryConfig()
    with pytest.raises(ValueError):
        getattr(g, setter)(0.0)


def test_corona_exclusion_is_the_angle_subtended_at_one_au():
    g = GeometryConfig().SetSepExclusion(3.0)
    assert g.GetCoronaExclusionKm() == pytest.approx(
        AU_KM * math.sin(math.radians(3.0))
    )


def test_larger_exclusion_angle_means_larger_miss_distance():
    small = GeometryConfig().SetSepExclusion(1.0).GetCoronaExclusionKm()
    large = GeometryConfig().SetSepExclusion(5.0).GetCoronaExclusionKm()
    assert large > small


def test_segment_distance_perpendicular_case():
    # C sits 3 units off the midpoint of a segment lying along x.
    a = np.array([[0.0, 0.0, 0.0]])
    b = np.array([[10.0, 0.0, 0.0]])
    c = np.array([[5.0, 3.0, 0.0]])
    assert segment_distances(a, b, c)[0] == pytest.approx(3.0)


def test_segment_distance_clamps_beyond_the_endpoints():
    # C is past B, so the nearest point on the segment is B itself.
    a = np.array([[0.0, 0.0, 0.0]])
    b = np.array([[10.0, 0.0, 0.0]])
    c = np.array([[20.0, 0.0, 0.0]])
    assert segment_distances(a, b, c)[0] == pytest.approx(10.0)


def test_segment_distance_is_vectorised():
    a = np.zeros((3, 3))
    b = np.tile([10.0, 0.0, 0.0], (3, 1))
    c = np.array([[5.0, 1.0, 0.0], [5.0, 2.0, 0.0], [5.0, 3.0, 0.0]])
    assert segment_distances(a, b, c) == pytest.approx([1.0, 2.0, 3.0])


def test_as_dict_includes_derived_exclusion_distance():
    d = GeometryConfig().AsDict()
    assert "corona_exclusion_km" in d
    assert d["corona_exclusion_km"] > 0
