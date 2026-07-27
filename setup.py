"""Setup file for SSBT.

This is needed because the project uses a flat-layout where the repo root
IS the ssbt package. The pyproject.toml alone cannot express the mapping
from ssbt -> . (the root directory) for editable installs, so we provide
this setup.py as a fallback for development installs.
"""

from setuptools import find_packages, setup

setup(
    # Flat layout: repo root = ssbt package. Each sub-directory is a sub-package.
    packages=[
        "ssbt",           # repo root
        "ssbt.analytics",
        "ssbt.core",
        "ssbt.data",
        "ssbt.examples",
        "ssbt.portfolio",
        "ssbt.strategy",
    ],
    package_dir={"ssbt": "."},
)
