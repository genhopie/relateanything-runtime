#!/usr/bin/env python3
"""Download locked visual inference artifacts and verify SHA-256 checksums (fail closed)."""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

from relateanything_runtime.config_keys import LOCKED_ARTIFACT_PINS

DETECTOR_REPO = "IDEA-Research/grounding-dino-base"
DETECTOR_REVISION = LOCKED_ARTIFACT_PINS["detector_revision"]
DETECTOR_WEIGHT_RELATIVE = "model.safetensors"

RELATION_REPO = "maelic/relsgg-vits16plus"
RELATION_WEIGHT_FILE = "model.pth"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def verify_file(path: Path, expected_sha256: str, label: str) -> None:
    if not path.is_file():
        raise SystemExit(f"fetch_artifacts: missing {label} at {path}")
    actual = sha256_file(path)
    if actual != expected_sha256.lower():
        raise SystemExit(f"fetch_artifacts: checksum mismatch for {label}: {actual} != {expected_sha256}")


def fetch_detector(dest: Path) -> None:
    from huggingface_hub import snapshot_download

    tmp_parent = dest.parent / ".download-tmp"
    tmp_parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(
        snapshot_download(
            repo_id=DETECTOR_REPO,
            revision=DETECTOR_REVISION,
            local_dir=str(tmp_parent / "detector-dl"),
            local_dir_use_symlinks=False,
        )
    )
    weight_src = tmp_dir / DETECTOR_WEIGHT_RELATIVE
    verify_file(weight_src, LOCKED_ARTIFACT_PINS["detector_weight_sha256"], "detector weights")
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(tmp_dir, dest)
    shutil.rmtree(tmp_parent, ignore_errors=True)
    verify_file(dest / DETECTOR_WEIGHT_RELATIVE, LOCKED_ARTIFACT_PINS["detector_weight_sha256"], "detector weights")


def fetch_relation(dest: Path) -> None:
    from huggingface_hub import snapshot_download

    tmp_parent = dest.parent / ".download-tmp"
    tmp_parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(
        snapshot_download(
            repo_id=RELATION_REPO,
            local_dir=str(tmp_parent / "relation-dl"),
            local_dir_use_symlinks=False,
        )
    )
    weight_src = tmp_dir / RELATION_WEIGHT_FILE
    verify_file(weight_src, LOCKED_ARTIFACT_PINS["relation_model_weight_sha256"], "relation weights")
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(tmp_dir, dest)
    shutil.rmtree(tmp_parent, ignore_errors=True)
    verify_file(dest / RELATION_WEIGHT_FILE, LOCKED_ARTIFACT_PINS["relation_model_weight_sha256"], "relation weights")


def main() -> int:
    root = Path(os.environ.get("RELATEANYTHING_ARTIFACT_ROOT", "artifacts")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    fetch_detector(root / "detector")
    fetch_relation(root / "relation")
    print(f"fetch_artifacts: OK under {root}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # noqa: BLE001 — CLI fail-closed surface
        print(f"fetch_artifacts: FAILED {error}", file=sys.stderr)
        return_code = 1
        sys.exit(return_code)
