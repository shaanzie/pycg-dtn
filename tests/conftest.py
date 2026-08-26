from __future__ import annotations

import os
from pathlib import Path

import pytest

_CACHE = Path(os.environ.get("PYCG_TEST_KERNELS", Path.cwd() / "kernels"))


@pytest.fixture(scope="session")
def mars_kernels(tmp_path_factory):
    """Kernels loaded for a Mars-orbiting satellite: LSK, PCK, GM, and the SPKs."""
    import spiceypy as sp

    from pycg_dtn.kernels import GM, LSK, PCK, PLANETS, SYSTEM_SPK, download

    needed = [LSK, PCK, GM, PLANETS, SYSTEM_SPK[4]]

    kernel_dir = _CACHE if _CACHE.is_dir() else tmp_path_factory.mktemp("kernels")
    for kernel in needed:
        if not (kernel_dir / kernel.filename).is_file():
            download(kernel, kernel_dir, progress=False)
        sp.furnsh(str(kernel_dir / kernel.filename))

    yield kernel_dir

    sp.kclear()
