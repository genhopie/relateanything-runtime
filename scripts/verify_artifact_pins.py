#!/usr/bin/env python3
"""Verify on-disk artifact checksums against contract section 15.7 pins."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

from relateanything_runtime.config_keys import LOCKED_ARTIFACT_PINS

PINS = {
    "relation/model.pth": LOCKED_ARTIFACT_PINS["relation_model_weight_sha256"],
    "detector/model.safetensors": LOCKED_ARTIFACT_PINS["detector_weight_sha256"],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    root = Path(os.environ.get("RELATEANYTHING_ARTIFACT_ROOT", "artifacts")).resolve()
    failures = 0
    for relative, expected in PINS.items():
        path = root / relative
        if not path.is_file():
            print(f"MISSING {path}")
            failures += 1
            continue
        actual = sha256(path).lower()
        if actual != expected:
            print(f"MISMATCH {path}: {actual} != {expected}")
            failures += 1
        else:
            print(f"OK {relative}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
