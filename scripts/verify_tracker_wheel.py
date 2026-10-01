#!/usr/bin/env python3
"""Verify installed trackers package version and locked wheel SHA-256."""

from __future__ import annotations

import hashlib
import importlib.metadata
import subprocess
import sys
import tempfile
from pathlib import Path

from relateanything_runtime.config_keys import LOCKED_ARTIFACT_PINS

EXPECTED_VERSION = "2.6.1"
EXPECTED_SHA256 = LOCKED_ARTIFACT_PINS["tracker_wheel_sha256"]


def main() -> int:
    installed = importlib.metadata.version("trackers")
    if installed != EXPECTED_VERSION:
        print(f"trackers version mismatch: {installed} != {EXPECTED_VERSION}")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        wheel_dir = Path(tmp)
        subprocess.run(
            [sys.executable, "-m", "pip", "download", f"trackers=={EXPECTED_VERSION}", "-d", str(wheel_dir), "--no-deps"],
            check=True,
            capture_output=True,
        )
        wheels = list(wheel_dir.glob("trackers-*.whl"))
        if len(wheels) != 1:
            print("expected exactly one trackers wheel download")
            return 1
        digest = hashlib.sha256()
        with wheels[0].open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        actual = digest.hexdigest().lower()
        if actual != EXPECTED_SHA256:
            print(f"wheel sha256 mismatch: {actual} != {EXPECTED_SHA256}")
            return 1
    print("trackers wheel verification OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
