# mypy: skip-file

import os
import sys

# Add your src/ directory to sys.path so autodoc can find mlsdk
sys.path.insert(0, os.path.abspath("../src"))

project = "Mindlytics SDK for Python"
author = "Andrew Peebles"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",  # For Google-style docstrings
    "sphinx.ext.viewcode",  # Optional: adds source code links
]

exclude_patterns = []
templates_path = ["_templates"]
html_static_path = ["_static"]

html_theme = "sphinx_rtd_theme"
