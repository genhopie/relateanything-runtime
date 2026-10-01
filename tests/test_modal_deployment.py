import os

import pytest

from relateanything_runtime.modal_app import (
    PRODUCTION_MODAL_ENVIRONMENT,
    PRODUCTION_MODAL_SECRET_NAME,
    RUNTIME_API_KEY_ENV,
    assert_modal_runtime_api_key_configured,
    modal_secret_name,
)
from relateanything_runtime.modal_state import DEFAULT_REGISTRY_IMAGE


def test_registry_image_uses_immutable_digest_reference() -> None:
    image_ref = os.environ.get("RELATEANYTHING_REGISTRY_IMAGE", DEFAULT_REGISTRY_IMAGE)
    assert "@sha256:" in image_ref
    assert "latest" not in image_ref
    assert image_ref.startswith("ghcr.io/genhopie/relateanything-runtime@sha256:")


def test_production_modal_secret_name() -> None:
    assert PRODUCTION_MODAL_SECRET_NAME == "relateanything-runtime-api"
    assert PRODUCTION_MODAL_ENVIRONMENT == "main"
    assert modal_secret_name() == PRODUCTION_MODAL_SECRET_NAME


def test_modal_secret_name_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RELATEANYTHING_MODAL_SECRET", "custom-secret")
    assert modal_secret_name() == "custom-secret"


def test_assert_modal_runtime_api_key_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(RUNTIME_API_KEY_ENV, raising=False)
    monkeypatch.delenv("RELATEANYTHING_MODAL_ALLOW_NO_SECRET", raising=False)
    with pytest.raises(RuntimeError, match=RUNTIME_API_KEY_ENV):
        assert_modal_runtime_api_key_configured()


def test_assert_modal_runtime_api_key_ok_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(RUNTIME_API_KEY_ENV, "configured-key")
    monkeypatch.delenv("RELATEANYTHING_MODAL_ALLOW_NO_SECRET", raising=False)
    assert_modal_runtime_api_key_configured()


def test_modal_deploy_workflow_references_secret_not_api_key_value() -> None:
    workflow_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        ".github",
        "workflows",
        "modal-deploy.yml",
    )
    with open(workflow_path, encoding="utf-8") as handle:
        workflow = handle.read()
    assert 'pip install -e ".[modal]"' in workflow
    install_pos = workflow.index('pip install -e ".[modal]"')
    deploy_pos = workflow.index("modal deploy --env main")
    assert install_pos < deploy_pos
    assert "MODAL_TOKEN_ID: ${{ secrets.MODAL_TOKEN_ID }}" in workflow
    assert "MODAL_TOKEN_SECRET: ${{ secrets.MODAL_TOKEN_SECRET }}" in workflow
    assert "RELATEANYTHING_REGISTRY_IMAGE: ${{ inputs.registry_image }}" in workflow
    assert "RELATEANYTHING_MODAL_SECRET: relateanything-runtime-api" in workflow
    assert "RELATEANYTHING_MODAL_ENVIRONMENT: main" in workflow
    assert (
        "modal deploy --env main src/relateanything_runtime/modal_app.py" in workflow
    )
    assert "RELATEANYTHING_RUNTIME_API_KEY:" not in workflow
