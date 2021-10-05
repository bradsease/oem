import setuptools
import os

with open("README.md", "r") as fh:
    long_description = fh.read()

version = 'v0.3.1'#os.environ.get("CI_COMMIT_TAG")[1:]
if version is None:
    raise ValueError("Version not found.")

setuptools.setup(
    name="oem",
    version=version,
    author="Brad Sease",
    author_email="bradsease@gmail.com",
    description="Python Orbit Ephemeris Message (OEM) tools",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bradsease/oem",
    packages=setuptools.find_packages(exclude=["tests"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Astronomy"
    ],
    python_requires='>=3.6',
    install_requires=[
        'numpy',
        'astropy',
        'lxml'
    ]
)
