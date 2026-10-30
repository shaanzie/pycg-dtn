"""Turn a link distance into a data rate.
"""

from __future__ import annotations

import numpy as np

#: Speed of light in vacuum, km/s]
C_KM_S = 299792.458

#: Boltzmann constant, J/K (exact, 2019 SI): https://physics.nist.gov/cgi-bin/cuu/Value?k
BOLTZMANN_J_K = 1.380649e-23


def _positive(name: str, value: float) -> float:
    value = float(value)
    if not np.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be a positive, finite number, got {value!r}")
    return value


def _finite(name: str, value: float) -> float:
    value = float(value)
    if not np.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {value!r}")
    return value


class LinkBudget:
    """Radio parameters for one direction of a link.

    A graph has a default budget for every link, and can override it per pair
    of node groups with ``ContactGraph.SetLinkBudgetFor``.
    """

    __slots__ = (
        "_tx_power_w",
        "_frequency_hz",
        "_bandwidth_hz",
        "_tx_gain_dbi",
        "_rx_gain_dbi",
        "_noise_psd_dbm_hz",
        "_min_rate_bps",
        "_max_rate_bps",
    )

    def __init__(
        self,
        *,
        tx_power_w: float = 100.0,
        frequency_hz: float = 8.42e9,
        bandwidth_hz: float = 1.0e6,
        tx_gain_dbi: float = 48.0,
        rx_gain_dbi: float = 74.18,
        noise_psd_dbm_hz: float = -174.0,
        min_rate_bps: float = 1.0,
        max_rate_bps: float | None = None,
    ) -> None:
        self._tx_power_w = _positive("tx_power_w", tx_power_w)
        self._frequency_hz = _positive("frequency_hz", frequency_hz)
        self._bandwidth_hz = _positive("bandwidth_hz", bandwidth_hz)
        self._tx_gain_dbi = _finite("tx_gain_dbi", tx_gain_dbi)
        self._rx_gain_dbi = _finite("rx_gain_dbi", rx_gain_dbi)
        self._noise_psd_dbm_hz = _finite("noise_psd_dbm_hz", noise_psd_dbm_hz)
        self._min_rate_bps = _positive("min_rate_bps", min_rate_bps)
        self._max_rate_bps = None
        if max_rate_bps is not None:
            self._max_rate_bps = _positive("max_rate_bps", max_rate_bps)


    def GetTxPower(self) -> float:
        """Transmitter output power, watts."""
        return self._tx_power_w

    def SetTxPower(self, watts: float) -> LinkBudget:
        """Set transmitter output power in watts."""
        self._tx_power_w = _positive("tx_power_w", watts)
        return self

    def GetTxGain(self) -> float:
        """Transmit antenna gain, dBi."""
        return self._tx_gain_dbi

    def SetTxGain(self, dbi: float) -> LinkBudget:
        """Set transmit antenna gain in dBi."""
        self._tx_gain_dbi = _finite("tx_gain_dbi", dbi)
        return self

    def GetRxGain(self) -> float:
        """Receive antenna gain, dBi."""
        return self._rx_gain_dbi

    def SetRxGain(self, dbi: float) -> LinkBudget:
        """Set receive antenna gain in dBi."""
        self._rx_gain_dbi = _finite("rx_gain_dbi", dbi)
        return self

    def GetNoisePsd(self) -> float:
        """Noise power spectral density, dBm/Hz."""
        return self._noise_psd_dbm_hz

    def SetNoisePsd(self, dbm_per_hz: float) -> LinkBudget:
        """Set noise power spectral density in dBm/Hz."""
        self._noise_psd_dbm_hz = _finite("noise_psd_dbm_hz", dbm_per_hz)
        return self

    def GetNoiseTemperature(self) -> float:
        """Receiver system noise temperature implied by the noise PSD, kelvin."""
        return 10.0 ** ((self._noise_psd_dbm_hz - 30.0) / 10.0) / BOLTZMANN_J_K

    def SetNoiseTemperature(self, kelvin: float) -> LinkBudget:
        """Set the noise PSD from a system noise temperature: N0 = k T."""
        kelvin = _positive("noise_temperature_k", kelvin)
        self._noise_psd_dbm_hz = 10.0 * np.log10(BOLTZMANN_J_K * kelvin) + 30.0
        return self

    def GetFrequency(self) -> float:
        """Carrier frequency, Hz."""
        return self._frequency_hz

    def SetFrequency(self, hz: float) -> LinkBudget:
        """Set carrier frequency in Hz."""
        self._frequency_hz = _positive("frequency_hz", hz)
        return self

    def GetBandwidth(self) -> float:
        """Channel bandwidth, Hz."""
        return self._bandwidth_hz

    def SetBandwidth(self, hz: float) -> LinkBudget:
        """Set channel bandwidth in Hz."""
        self._bandwidth_hz = _positive("bandwidth_hz", hz)
        return self

    def GetMinRate(self) -> float:
        """Rate floor below which a contact is discarded, bits/s."""
        return self._min_rate_bps

    def SetMinRate(self, bps: float) -> LinkBudget:
        """Set the rate floor in bits/s."""
        self._min_rate_bps = _positive("min_rate_bps", bps)
        return self

    def GetMaxRate(self) -> float | None:
        """Rate cap, e.g. the radio's highest supported rate, bits/s; None = no cap."""
        return self._max_rate_bps

    def SetMaxRate(self, bps: float | None) -> LinkBudget:
        """Set the rate cap in bits/s, or None to remove it."""
        if bps is None:
            self._max_rate_bps = None
        else:
            self._max_rate_bps = _positive("max_rate_bps", bps)
        return self

    def GetWavelength(self) -> float:
        """Carrier wavelength, metres."""
        return (C_KM_S * 1000.0) / self._frequency_hz

    def GetNoisePower(self) -> float:
        """Total in-band noise power, dBm."""
        return self._noise_psd_dbm_hz + 10.0 * np.log10(self._bandwidth_hz)

    def RateBps(self, range_km: np.ndarray | float) -> np.ndarray:
        """Shannon capacity over a free-space link of the given range(s),
        capped at the max rate if one is set."""
        r_m = np.maximum(np.asarray(range_km, dtype=float) * 1000.0, 1.0)

        # Friis: P_rx = P_tx * G_tx * G_rx * (lambda / 4 pi R)^2
        fspl_linear = (self.GetWavelength() / (4.0 * np.pi * r_m)) ** 2
        rx_dbm = (
            10.0 * np.log10(self._tx_power_w * fspl_linear)
            + 30.0
            + self._tx_gain_dbi
            + self._rx_gain_dbi
        )
        snr_linear = 10.0 ** ((rx_dbm - self.GetNoisePower()) / 10.0)
        rate = self._bandwidth_hz * np.log2(1.0 + snr_linear)
        if self._max_rate_bps is not None:
            rate = np.minimum(rate, self._max_rate_bps)
        return rate


    def AsDict(self) -> dict[str, float]:
        """All parameters, for embedding in output metadata."""
        return {
            "tx_power_w": self._tx_power_w,
            "frequency_hz": self._frequency_hz,
            "bandwidth_hz": self._bandwidth_hz,
            "tx_gain_dbi": self._tx_gain_dbi,
            "rx_gain_dbi": self._rx_gain_dbi,
            "noise_psd_dbm_hz": self._noise_psd_dbm_hz,
            "min_rate_bps": self._min_rate_bps,
            "max_rate_bps": self._max_rate_bps,
        }

    def __repr__(self) -> str:
        return (
            f"LinkBudget(tx_power_w={self._tx_power_w:g}, "
            f"frequency_hz={self._frequency_hz:g}, "
            f"bandwidth_hz={self._bandwidth_hz:g}, "
            f"tx_gain_dbi={self._tx_gain_dbi:g}, "
            f"rx_gain_dbi={self._rx_gain_dbi:g}, "
            f"noise_psd_dbm_hz={self._noise_psd_dbm_hz:g}, "
            f"min_rate_bps={self._min_rate_bps:g}, "
            f"max_rate_bps={self._max_rate_bps})"
        )
