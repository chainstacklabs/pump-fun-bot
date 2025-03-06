from setuptools import find_packages, setup

setup(
    name="pump_bot",
    version="0.1",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
)
