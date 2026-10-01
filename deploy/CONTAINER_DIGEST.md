# Container image digest (production gate)

Build the immutable production image from repository `main` and record the digest here for Base Admin `content_visual_inference_runtime_container_revision`.

```bash
docker build -t ghcr.io/genhopie/relateanything-runtime:$(git rev-parse --short HEAD) .
docker push ghcr.io/genhopie/relateanything-runtime:$(git rev-parse --short HEAD)
docker inspect --format='{{index .RepoDigests 0}}' ghcr.io/genhopie/relateanything-runtime:$(git rev-parse --short HEAD)
```

**Agent delivery note:** Docker was not available in the Agent4 execution environment; no digest was produced in this session. CI or manual build must fill this file before production activation.
