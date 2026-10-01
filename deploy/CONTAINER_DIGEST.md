# Container image digest (production gate)

Build the immutable production image from repository `main` and record the **exact** digest below for Base Admin `content_visual_inference_runtime_container_revision`.

## Build (local or CI)

```bash
docker build -t ghcr.io/genhopie/relateanything-runtime:$(git rev-parse HEAD) .
docker inspect --format='{{.Id}}' ghcr.io/genhopie/relateanything-runtime:$(git rev-parse HEAD)
```

GitHub Actions workflow `container-build` on `main` prints the digest in the job summary after each push. Copy that value here when promoting a release.

## Recorded production digest

_Not set in this repository commit — populate only after a verified image build (no placeholder digests)._
