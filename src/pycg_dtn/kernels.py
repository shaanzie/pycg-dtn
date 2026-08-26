"""Work out which SPICE kernels a set of celestials needs, then fetch them.

All files come from NAIF's public generic-kernel archive,
https://naif.jpl.nasa.gov/pub/naif/generic_kernels/
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import requests
import spiceypy as sp

from .celestials import SYSTEM_NAMES, Celestial

NAIF_ROOT = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels"


class KernelError(RuntimeError):
    """Raised when a kernel cannot be fetched, or does not cover what it should."""


@dataclass(frozen=True)
class Kernel:
    """One SPICE kernel file in NAIF's generic archive."""

    filename: str
    path: str  
    purpose: str
    approx_mb: float

    @property
    def url(self) -> str:
        return f"{NAIF_ROOT}/{self.path}/{self.filename}"


#: Leap seconds, needed for any UTC <-> ephemeris-time conversion.
LSK = Kernel(
    "naif0012.tls", "lsk", "leap seconds, for UTC <-> ET conversion", 0.005
)

#: Body radii and IAU body-fixed frames, needed for occultation geometry.
PCK = Kernel(
    "pck00011.tpc", "pck", "body radii and IAU body-fixed orientation", 0.13
)

#: Gravitational parameters, needed to propagate a satellite's orbit.
GM = Kernel(
    "gm_de440.tpc", "pck", "gravitational parameters (GM) for orbit propagation", 0.012
)

#: Planetary ephemeris. Covers the Sun, the inner planets, and Earth's Moon.
PLANETS = Kernel(
    "de440s.bsp",
    "spk/planets",
    "planetary ephemeris DE440 (short), 1849-2150",
    31.2,
)

PLANETS_PROVIDES = frozenset({10, 199, 299, 301, 399})

SYSTEM_SPK: dict[int, Kernel] = {
    4: Kernel("mar099s.bsp", "spk/satellites", "Phobos and Deimos", 64.5),
    5: Kernel("jup365.bsp", "spk/satellites", "regular Jovian satellites", 1083.9),
    6: Kernel("sat441.bsp", "spk/satellites", "major Saturnian satellites", 630.9),
    7: Kernel("ura116xl.bsp", "spk/satellites", "major Uranian satellites", 659.5),
    8: Kernel("nep097.bsp", "spk/satellites", "major Neptunian satellites", 100.4),
    9: Kernel("plu060.bsp", "spk/satellites", "Pluto system", 128.9),
}


def required_for(
    celestials: list[Celestial], satellites: list | None = None
) -> list[Kernel]:
    """The kernels needed to place every one of ``celestials`` in space."""
    kernels = [LSK, PCK, PLANETS]

    if satellites:
        kernels.append(GM)

    # A satellite's central body has to be locatable even if it is not a node
    bodies = list(celestials) + [s.central for s in satellites or []]

    needs_satellites: set[int] = set()
    for body in bodies:
        if body.naif_id in PLANETS_PROVIDES:
            continue
        if body.naif_id < 10:
            continue
        if body.system:
            needs_satellites.add(body.system)

    for system in sorted(needs_satellites):
        kernel = SYSTEM_SPK.get(system)
        if kernel is None:
            raise KernelError(
                f"no generic satellite ephemeris is registered for the "
                f"{SYSTEM_NAMES.get(system, system)} system"
            )
        kernels.append(kernel)

    return kernels


_CA_CANDIDATES = (
    os.environ.get("REQUESTS_CA_BUNDLE"),
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
)


def _ca_bundle() -> str | bool:
    """Pick a usable CA bundle, falling back to whatever requests defaults to."""
    for path in _CA_CANDIDATES:
        if path and Path(path).is_file():
            return path
    return True


def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def download(
    kernel: Kernel,
    kernel_dir: Path,
    *,
    verify: str | bool | None = None,
    progress: bool = True,
) -> Path:
    """Stream one kernel to ``kernel_dir``, skipping it if already complete."""
    kernel_dir = Path(kernel_dir)
    kernel_dir.mkdir(parents=True, exist_ok=True)
    dest = kernel_dir / kernel.filename
    verify = _ca_bundle() if verify is None else verify

    try:
        head = requests.head(kernel.url, allow_redirects=True, timeout=30, verify=verify)
        head.raise_for_status()
    except requests.RequestException as exc:
        raise KernelError(f"could not reach {kernel.url}: {exc}") from exc
    remote_size = int(head.headers.get("content-length", 0))

    if dest.exists() and remote_size and dest.stat().st_size == remote_size:
        if progress:
            print(f"  [skip] {kernel.filename} already complete ({_human(remote_size)})")
        return dest

    if progress:
        size = _human(remote_size) if remote_size else "?"
        print(f"  [get ] {kernel.filename} ({size})  -- {kernel.purpose}", flush=True)

    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with requests.get(kernel.url, stream=True, timeout=120, verify=verify) as r:
            r.raise_for_status()
            done = 0
            with tmp.open("wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    fh.write(chunk)
                    done += len(chunk)
                    if progress and remote_size:
                        pct = 100 * done / remote_size
                        print(
                            f"\r         {pct:5.1f}%  {_human(done)}", end="", flush=True
                        )
            if progress and remote_size:
                print()
    except requests.RequestException as exc:
        tmp.unlink(missing_ok=True)
        raise KernelError(f"download of {kernel.filename} failed: {exc}") from exc

    tmp.rename(dest)
    return dest


def fetch(
    kernels: list[Kernel],
    kernel_dir: Path,
    *,
    progress: bool = True,
) -> list[Path]:
    """Download every kernel in ``kernels`` that is not already present."""
    verify = _ca_bundle()
    return [
        download(k, kernel_dir, verify=verify, progress=progress) for k in kernels
    ]



def furnish(kernels: list[Kernel], kernel_dir: Path) -> None:
    """Load the kernels into the SPICE subsystem."""
    kernel_dir = Path(kernel_dir)
    for kernel in kernels:
        path = kernel_dir / kernel.filename
        if not path.is_file():
            raise KernelError(
                f"missing kernel {path}; fetch it first "
                f"(ContactGraph.FetchKernels(), or `pycg fetch`)"
            )
        sp.furnsh(str(path))


def verify_coverage(
    celestials: list[Celestial], kernels: list[Kernel], kernel_dir: Path
) -> None:
    """Check the required SPKs actually contain every requested body."""
    kernel_dir = Path(kernel_dir)
    covered: set[int] = set()
    for kernel in kernels:
        if not kernel.filename.endswith(".bsp"):
            continue
        path = kernel_dir / kernel.filename
        try:
            covered.update(int(i) for i in sp.spkobj(str(path)))
        except Exception:  
            continue

    missing = [b for b in celestials if b.naif_id not in covered]
    if missing:
        names = ", ".join(f"{b.name} ({b.naif_id})" for b in missing)
        have = ", ".join(k.filename for k in kernels if k.filename.endswith(".bsp"))
        raise KernelError(
            f"no required ephemeris covers: {names} (loaded: {have}). "
            "The kernel registry may be out of date with NAIF's archive."
        )
