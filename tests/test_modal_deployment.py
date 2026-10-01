import os

from relateanything_runtime.modal_state import DEFAULT_REGISTRY_IMAGE


def test_registry_image_uses_immutable_digest_reference() -> None:
    image_ref = os.environ.get("RELATEANYTHING_REGISTRY_IMAGE", DEFAULT_REGISTRY_IMAGE)
    assert "@sha256:" in image_ref
    assert "latest" not in image_ref
    assert image_ref.startswith("ghcr.io/genhopie/relateanything-runtime@sha256:")
