# Repository Guide

## Overview

`oem` is a Python library for reading, writing, converting, comparing, and sampling CCSDS Orbit Ephemeris Message (OEM) files. Core package code is in `oem/`; tests and sample OEM files are in `tests/`.

## Development

- Use `uv` and the default virtual environment, `.venv`, for all code execution and testing.
- Set up the environment with `uv venv` and install dependencies with `uv pip install -e ".[test,tle]" black`.
- Run tests with `uv run pytest`.
- Run lint checks with `uv run flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`.
- Format all Python code with Black: `uv run black .`.
- Use Black for all code formatting; do not introduce unrelated formatting changes.
