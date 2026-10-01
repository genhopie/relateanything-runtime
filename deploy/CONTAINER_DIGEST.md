# Container image digest (production gate)

The immutable **GitHub Container Registry** digest for the image built from `main` is the only authority for Base Admin `content_visual_inference_runtime_container_revision`.

## CI publish (`container-build` on `main`)

- Image: `ghcr.io/genhopie/relateanything-runtime:<git-sha>`
- Digest: `sha256:…` from the `docker/build-push-action` push result (workflow job output `digest`)
- The workflow **fails** if no registry `sha256` digest is available (local `docker image inspect` IDs are not used)

## Recorded production digest

| Field | Value |
| --- | --- |
| Runtime git revision | `960618fddca3c99fe90be03f4d42793a7a8b1dad` |
| Registry image reference | `ghcr.io/genhopie/relateanything-runtime:960618fddca3c99fe90be03f4d42793a7a8b1dad` |
| Immutable registry digest | `sha256:37b3edec8612f22113478e47a98a65e4f6c5bd0d31e63cbd8d4d5e16049f0c9a` |
| Verified publish | GitHub Actions `container-build` run [36835049756](https://github.com/genhopie/relateanything-runtime/actions/runs/36835049756) on `2026-10-01` |

Set Base Admin `content_visual_inference_runtime_container_revision` to the **immutable registry digest** exactly (`sha256:…`).
