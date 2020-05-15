import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="oem",
    version="0.1.0",
    author="Brad Sease",
    author_email="bradsease@gmail.com",
    description="Python Orbital Ephemeris Message (OEM) tools",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bradsease/oem",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.0',
)
