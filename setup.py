"""Setup file for SSBT - flat layout where repo root IS the ssbt package."""

from setuptools import setup

setup(
    # Flat layout: repo root = ssbt package. Each sub-directory is a sub-package.
    packages=[
        "ssbt",
        "ssbt.analytics",
        "ssbt.core",
        "ssbt.data",
        "ssbt.events",
        "ssbt.examples",
        "ssbt.experiments",
        "ssbt.experiments.examples",
        "ssbt.outcomes",
        "ssbt.portfolio",
        "ssbt.strategy",
    ],
    package_dir={"ssbt": "ssbt"},
)