# Contributing to PyCG-DTN

Thanks for your interest. Bug reports, kernel-registry updates and new geometry
features are all welcome.

## Getting set up

```bash
git clone https://github.com/shaanzie/pycg-dtn.git
cd pycg-dtn
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running the tests

Most tests are pure logic and run in well under a second:

```bash
pytest -m "not network"
```

Tests marked `network` download kernels from NAIF and are slower. Run them before
opening a PR that touches `kernels.py`:

```bash
pytest -m network
```

## Pull requests

- Keep the public API in the existing `PascalCase` style (`AddCelestial`,
  `GetLinkBudget`, `GenerateContactGraph`); internal helpers stay `snake_case`.
- New configuration values get a `Get*`/`Set*` pair with validation, and go into
  the relevant `AsDict()` so they land in output metadata.
- Add a test that would have failed before your change.
- Cite a source in a comment for any physical constant or model parameter.

## License

By contributing you agree that your contributions are licensed under the
GNU General Public License v3.0 or later, the same terms as the project.
