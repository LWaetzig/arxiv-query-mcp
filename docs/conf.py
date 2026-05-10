import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

# Project information
project = "arxiv-query-mcp"
author = "Lucas Waetzig"
copyright = "2024, Lucas Waetzig"
release = "1.0.0"
version = "1.0"

# General configuration
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Autodoc
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
    "member-order": "bysource",
}
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = False
napoleon_use_rtype = False
napoleon_use_ivar = True

autodoc_mock_imports = ["pydantic", "httpx", "mcp"]

suppress_warnings = [
    "ref.duplicate",          # frozen dataclass fields documented twice by Sphinx 9
    "autodoc.failed_method",  # pydantic @field_validator classmethods have no resolvable signature
]

# Intersphinx
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pydantic": ("https://docs.pydantic.dev/latest", None),
}

# HTML output
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_title = "arxiv-query-mcp"
html_short_title = "arxiv-query-mcp"

html_theme_options = {
    "prev_next_buttons_location": "bottom",
    "style_external_links": True,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "navigation_depth": 3,
    "includehidden": True,
    "titles_only": False,
}

html_context = {
    "display_github": True,
    "github_user": "LWaetzig",
    "github_repo": "arxiv-mcp",
    "github_version": "main",
    "conf_py_path": "/docs/",
}
