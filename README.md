# relateanything-runtime

Public AGPL **Corresponding Source** for the Content Intelligence advanced video visual inference HTTP runtime consumed by `genhopie/base` (`content_visual_inference`).

## HTTP contract

- `POST /control-plane` — Base AI Gateway adapter (`operation=submit|status|cancel`); maps to the same job authority as `/v1/jobs`.
- `POST /v1/jobs` — requires `Idempotency-Key` (Base CI `processing_job_id`); body matches Base visual submit payload.
- `GET /v1/jobs/{executionId}` — status, provenance, usage, normalized observations on success.
- `DELETE /v1/jobs/{executionId}` — idempotent cancel; terminal jobs remain terminal.
- `GET /healthz` — liveness.

Optional `Authorization: Bearer <API key>` when `RELATEANYTHING_RUNTIME_API_KEY` is set in the deployment environment (matches Base `content_visual_inference_api_key`).

Processing configuration is **fully governed** from the request (`processingConfiguration`); the runtime does not embed operational defaults.

## Locked artifact pins (contract §15.7)

| Component | Pin |
|-----------|-----|
| RelateAnything upstream git | `e9ea42aed60f766f12ad19d51709129c50110a3b` |
| Relation `model.pth` SHA-256 | `5d281bf0d89f2bbfd72ff5a14f9a40ce12534e790b0402e2ca970539c7bcc294` |
| Grounding DINO revision | `c0605c367b39f7589694dfcb61046322dc07ac4a` |
| `model.safetensors` SHA-256 | `5548f844c928c4b6f411fa8cbcc2bfa8dbbba437cb1d513975519f93c2a9ed21` |
| Tracker | `trackers==2.6.1` (wheel SHA-256 `b5188de630f449958be3ce787fbb0375c69cfde094b6e4b4329cd79a98108501`) |

## Local development

```bash
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
pytest
```

Set `RELATEANYTHING_ARTIFACT_ROOT` to a directory containing verified `relation/model.pth` and `detector/model.safetensors` (see `scripts/verify_artifact_pins.py`).

## Production container (GitHub Container Registry)

On every push to `main`, the `container-build` workflow:

1. builds the Dockerfile in this repository (including artifact fetch + checksum verification inside the image);
2. publishes to `ghcr.io/genhopie/relateanything-runtime:<git-sha>`;
3. fails if no immutable registry `sha256:…` digest is produced;
4. writes the digest to the workflow summary and job outputs.

The **registry digest** (`sha256:…` from the pushed image) is the only value accepted for Base Admin `content_visual_inference_runtime_container_revision`. Do not use the git SHA, image tag, or a local `docker image inspect` ID.

After a successful workflow run, copy the digest recorded in `deploy/CONTAINER_DIGEST.md` (updated for the promoted build) into Admin/API Management.

## Modal production deployment (scale-to-zero GPU)

Production HTTP is deployed with [Modal](https://modal.com/) using the immutable GHCR image reference:

`ghcr.io/genhopie/relateanything-runtime@sha256:<digest>`

Set `RELATEANYTHING_REGISTRY_IMAGE` to that exact `@sha256:…` reference before deploy. Modal pulls the registry image as the inference identity; do not mount alternate source for production inference behavior.

- App entrypoint: `src/relateanything_runtime/modal_app.py`
- GPU worker: `run_visual_job_gpu` on `T4`, `scaledown_window=60` (scale to zero when idle)
- Web ASGI: `serve_fastapi` exposes the existing FastAPI app (including `/control-plane`)
- Durable metadata: Modal `Dict` (`relateanything-runtime-job-state`) stores execution metadata and idempotency mappings only — **not** signed URLs or raw video
- Async execution: `FunctionCall.spawn` with cancellation via `FunctionCall.cancel`

Manual deploy (requires repository secrets `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET`):

```bash
pip install "modal>=0.73.0"
export RELATEANYTHING_REGISTRY_IMAGE="ghcr.io/genhopie/relateanything-runtime@sha256:..."
modal deploy src/relateanything_runtime/modal_app.py
```

Or run the `modal-deploy` GitHub Actions workflow with the verified digest input.

Base Admin (manual, not written by this repo):

- `content_visual_inference_endpoint_url` — Modal web endpoint URL for `serve_fastapi`
- `content_visual_inference_api_key` — bearer token matching `RELATEANYTHING_RUNTIME_API_KEY`
- `content_visual_inference_runtime_container_revision` — exact GHCR `sha256:…` digest of the deployed inference image

## License

AGPL-3.0 for this repository's runtime modifications. See `NOTICE` and `THIRD_PARTY_NOTICES.md`. RelateAnything upstream is AGPL; relation weights remain subject to the separate DINOv3 license.
