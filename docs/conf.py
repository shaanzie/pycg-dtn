# Sphinx configuration. See https://www.sphinx-doc.org/en/master/usage/configuration.html

from importlib.metadata import version as _version

project = "PyCG-DTN"
author = "Ishaan Lagwankar, Griffin Klevering"
copyright = "2026, Ishaan Lagwankar, Griffin Klevering"

release = _version("pycg-dtn")
version = ".".join(release.split(".")[:2])

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
]

# Pages are written in Markdown
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
master_doc = "index"

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

myst_enable_extensions = ["colon_fence", "deflist"]
myst_heading_anchors = 3

html_theme = "furo"
html_title = f"PyCG-DTN {release}"
html_static_path = ["_static"]

# Most of this API documents itself through type hints rather than docstrings
autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
always_use_bars_union = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable", None),
}

# spiceypy has no published objects.inv, so its names cannot resolve
nitpick_ignore_regex = [("py:class", r"spiceypy\..*")]
