# Container image digest (production gate)

Build the immutable production image from repository `main` and record the **exact** digest below for Base Admin `content_visual_inference_runtime_container_revision`.

## Build (local or CI)

```bash
docker build -t ghcr.io/genhopie/relateanything-runtime:$(git rev-parse HEAD) .
docker inspect --format='{{.Id}}' ghcr.io/genhopie/relateanything-runtime:$(git rev-parse HEAD)
```

GitHub Actions workflow `container-build` on `main` prints the digest in the job summary after each push. Copy that value here when promoting a release.

## Recorded production digest

| Field | Value |
| --- | --- |
| Runtime git revision | `2e42d7d846542c0807577b93dc56d1add451acff` |
| Image reference (local build tag) | `ghcr.io/genhopie/relateanything-runtime:2e42d7d846542c0807577b93dc56d1add451acff` |
| Immutable digest (`docker image inspect --format='{{.Id}}'`) | `sha256:e3681a25fa60a93a2a8ac5ba4afdf402f19a7e05e5c06fb8796eda7a0228b554` |
| Verified build | GitHub Actions `container-build` run [36832818024](https://github.com/genhopie/relateanything-runtime/actions/runs/36832818024) on `2026-10-01` |

Use the digest value for Base Admin `content_visual_inference_runtime_container_revision`. The workflow builds on `main` push; publish to a registry separately if remote `RepoDigests` are required.
