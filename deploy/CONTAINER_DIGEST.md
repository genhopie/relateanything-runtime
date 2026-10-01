# Container image digest (production gate)

The immutable **GitHub Container Registry** digest for the image built from `main` is the only authority for Base Admin `content_visual_inference_runtime_container_revision`.

## CI publish (`container-build` on `main`)

- Image: `ghcr.io/genhopie/relateanything-runtime:<git-sha>`
- Digest: `sha256:…` from the `docker/build-push-action` push result (workflow job output `digest`)
- The workflow **fails** if no registry `sha256` digest is available (local `docker image inspect` IDs are not used)

Copy the digest from the successful workflow run summary or job outputs into **Recorded production digest** below when promoting a build.

## Recorded production digest

_Updated after the first registry publish on `main` with workflow changes from Prompt CI-ADV-VIDEO-RUNTIME-DEPLOYMENT-01._
