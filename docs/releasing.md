# Releasing

Pushing a tag that matches the version in `pyproject.toml` publishes the package
to PyPI. Tags may include a `v` prefix; for example, version `0.4.6` can be
released with either `0.4.6` or `v0.4.6`.

Before the first release, create a PyPI API token scoped to the `oem` project:

1. Sign in to [PyPI](https://pypi.org/manage/account/token/).
2. Create a token with the scope set to `Project: oem`.
3. Copy the token value, which begins with `pypi-`.

In GitHub, configure the secret used by the workflow:

1. Open the repository's **Settings**, then **Environments**.
2. Create an environment named `pypi`.
3. In that environment, add an Actions secret named `PYPI_API_TOKEN` with the
   PyPI token as its value.
4. Optionally require reviewers for the `pypi` environment to approve each
   upload.

After updating `pyproject.toml` to the release version and merging it to the
release branch, create and push the matching tag:

```shell
git tag v0.4.6
git push origin v0.4.6
```

The GitHub Actions workflow builds source and wheel distributions, verifies
them with Twine, and uploads them to PyPI.
