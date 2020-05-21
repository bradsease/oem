import setuptools
import os

with open("README.md", "r") as fh:
    long_description = fh.read()

version = os.environ.get("CI_COMMIT_TAG")[1:]
if version is None:
    raise ValueError("Version not found.")

setuptools.setup(
    name="oem",
    version=version,
    author="Brad Sease",
    author_email="bradsease@gmail.com",
    description="Python Orbital Ephemeris Message (OEM) tools",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bradsease/oem",
    packages=setuptools.find_packages(exclude=["tests"]),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.0',
)
