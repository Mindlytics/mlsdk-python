# mypy: skip-file

import os
import sys
import tomllib
from pathlib import Path
import datetime

# for pyproject.toml
sys.path.insert(0, os.path.abspath(".."))
# Add your src/ directory to sys.path so autodoc can find mlsdk
sys.path.insert(0, os.path.abspath("../src"))


# Read version from pyproject.toml
def get_version_from_pyproject():
    """Extract the version from pyproject.toml"""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"

    with open(pyproject_path, "rb") as f:  # Note: must open in binary mode
        pyproject_data = tomllib.load(f)

    # Get version from [tool.poetry] section
    return pyproject_data["project"]["version"]


project = "Mindlytics SDK for Python"
author = "Andrew Peebles"
release = get_version_from_pyproject()
version = ".".join(release.split(".")[:2])

current_year = datetime.datetime.now().year
copyright = f"{current_year}, Mindlytics AI"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",  # For Google-style docstrings
    "sphinx.ext.viewcode",  # Optional: adds source code links
]

exclude_patterns = []
templates_path = ["_templates"]
html_static_path = ["_static"]

html_theme = "sphinx_rtd_theme"
