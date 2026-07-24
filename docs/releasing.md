# Releasing

Pushing a tag that matches the version in `pyproject.toml` publishes the package
to PyPI. Tags may include a `v` prefix; for example, version `0.4.6` can be
released with either `0.4.6` or `v0.4.6`.

Before the first release, configure PyPI Trusted Publishing:

1. Sign in to PyPI and open the `oem` project's
   [Publishing settings](https://pypi.org/manage/project/oem/settings/publishing/).
2. Add a GitHub Actions trusted publisher with these values:
   - Owner: `bradsease`
   - Repository: `oem`
   - Workflow: `publish-pypi.yml`
   - Environment: `pypi`
3. If `oem` has not yet been created on PyPI, add the same values as a pending
   publisher from PyPI's Publishing page instead.

No GitHub or PyPI API token is required. GitHub exchanges a short-lived OIDC
token for a PyPI upload token only after PyPI verifies the trusted-publisher
configuration.

1. Open the repository's **Settings**, then **Environments**.
2. Create an environment named `pypi`.
3. Optionally require reviewers for the `pypi` environment to approve each
   upload.

After updating `pyproject.toml` to the release version and merging it to the
release branch, create and push the matching tag:

```shell
git tag v0.4.6
git push origin v0.4.6
```

The GitHub Actions workflow builds source and wheel distributions, verifies
them with Twine, then publishes the verified artifacts through PyPI Trusted
Publishing.
