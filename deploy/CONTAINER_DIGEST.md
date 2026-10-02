# Container image digest (production gate)

The immutable **GitHub Container Registry** digest for the image built from `main` is the only authority for Base Admin `content_visual_inference_runtime_container_revision`.

## CI publish (`container-build` on `main`)

- Image: `ghcr.io/genhopie/relateanything-runtime:<git-sha>`
- Digest: `sha256:…` from the `docker/build-push-action` push result (workflow job output `digest`)
- The workflow **fails** if no registry `sha256` digest is available (local `docker image inspect` IDs are not used)

## Recorded production digest

| Field | Value |
| --- | --- |
| Runtime git revision (image build) | `e68c8190985872fc1a3b79df261ba0f4c238e075` |
| Immutable registry image | `ghcr.io/genhopie/relateanything-runtime@sha256:ee0aac50480a1815a56405c4b9f03a21f51004b3d06cdd011b90bc98fd335b84` |
| Mutable tag (non-authoritative) | `ghcr.io/genhopie/relateanything-runtime:e68c8190985872fc1a3b79df261ba0f4c238e075` |
| Verified publish | GitHub Actions `container-build` run [36999111391](https://github.com/genhopie/relateanything-runtime/actions/runs/36999111391) on `2026-10-02` |

Modal production deploy must set `RELATEANYTHING_REGISTRY_IMAGE` to the immutable registry image row above (or a newer verified `@sha256:…` after a subsequent image rebuild).

Set Base Admin `content_visual_inference_runtime_container_revision` to the **immutable registry digest** exactly (`sha256:…`).
