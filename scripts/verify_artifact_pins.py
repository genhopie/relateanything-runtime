#!/usr/bin/env python3
"""Verify on-disk artifact checksums against contract section 15.7 pins."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

PINS = {
    "relation/model.pth": "5d281bf0d89f2bbfd72ff5a14f9a40ce12534e790b0402e2ca970539c7bcc294",
    "detector/model.safetensors": "5548f844c928c4b6f411fa8cbcc2bfa8dbbba437cb1d513975519f93c2a9ed21",
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
