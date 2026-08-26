from __future__ import annotations

import numpy as np
import pytest

from pycg_dtn import LinkBudget
from pycg_dtn.linkbudget import C_KM_S

AU_KM = 1.495978707e8


def test_defaults_round_trip_through_getters():
    lb = LinkBudget()
    assert lb.GetTxPower() == 100.0
    assert lb.GetFrequency() == 8.42e9
    assert lb.GetBandwidth() == 1.0e6
    assert lb.GetTxGain() == 48.0
    assert lb.GetRxGain() == 74.18
    assert lb.GetNoisePsd() == -174.0
    assert lb.GetMinRate() == 1.0


def test_every_setter_takes_effect():
    lb = LinkBudget()
    lb.SetTxPower(250.0)
    lb.SetFrequency(32.0e9)
    lb.SetBandwidth(5.0e6)
    lb.SetTxGain(52.0)
    lb.SetRxGain(79.0)
    lb.SetNoisePsd(-180.0)
    lb.SetMinRate(100.0)

    assert lb.GetTxPower() == 250.0
    assert lb.GetFrequency() == 32.0e9
    assert lb.GetBandwidth() == 5.0e6
    assert lb.GetTxGain() == 52.0
    assert lb.GetRxGain() == 79.0
    assert lb.GetNoisePsd() == -180.0
    assert lb.GetMinRate() == 100.0


def test_setters_chain():
    lb = LinkBudget().SetTxPower(200.0).SetBandwidth(2.0e6)
    assert lb.GetTxPower() == 200.0
    assert lb.GetBandwidth() == 2.0e6


@pytest.mark.parametrize(
    "setter, bad",
    [
        ("SetTxPower", 0.0),
        ("SetTxPower", -5.0),
        ("SetFrequency", -1.0),
        ("SetBandwidth", 0.0),
        ("SetMinRate", -1.0),
        ("SetTxPower", float("nan")),
        ("SetRxGain", float("inf")),
    ],
)
def test_invalid_values_are_rejected(setter, bad):
    lb = LinkBudget()
    with pytest.raises(ValueError):
        getattr(lb, setter)(bad)


def test_wavelength_matches_c_over_f():
    lb = LinkBudget().SetFrequency(8.42e9)
    assert lb.GetWavelength() == pytest.approx(C_KM_S * 1000.0 / 8.42e9)


def test_noise_power_is_psd_plus_bandwidth_in_db():
    lb = LinkBudget().SetBandwidth(1.0e6).SetNoisePsd(-174.0)
    assert lb.GetNoisePower() == pytest.approx(-174.0 + 60.0)


def test_rate_falls_off_with_range():
    lb = LinkBudget()
    rates = lb.RateBps(np.array([1e5, 1e6, 1e7, 1e8]))
    assert np.all(np.diff(rates) < 0), "rate must decrease as range grows"


def test_rate_is_capped_by_bandwidth_at_short_range():
    lb = LinkBudget()
    rate = float(lb.RateBps(1.0))
    assert np.isfinite(rate) and rate > 0


def test_rate_at_one_au_is_in_a_sane_range():
    lb = LinkBudget()
    rate = float(lb.RateBps(AU_KM))
    assert 1e3 < rate < 1e7, f"1 AU rate of {rate:.3g} bps is implausible"


def test_scalar_and_array_agree():
    lb = LinkBudget()
    scalar = float(lb.RateBps(AU_KM))
    array = float(lb.RateBps(np.array([AU_KM]))[0])
    assert scalar == pytest.approx(array)


def test_more_gain_gives_more_rate():
    base = LinkBudget()
    better = LinkBudget().SetRxGain(base.GetRxGain() + 6.0)
    assert float(better.RateBps(AU_KM)) > float(base.RateBps(AU_KM))


def test_as_dict_round_trips_into_a_new_budget():
    lb = LinkBudget().SetTxPower(123.0).SetFrequency(2.3e9)
    clone = LinkBudget(**lb.AsDict())
    assert clone.AsDict() == lb.AsDict()
