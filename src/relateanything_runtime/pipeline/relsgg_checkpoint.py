"""Load locked relation checkpoints into the installed relsgg package.

Released ``model.pth`` files may name DINOv3 blocks as either ``backbone.model.layer`` or
``backbone.model.model.layer`` depending on the ``transformers`` build. Adapt only that
prefix at load time so strict loading succeeds without substituting weights or revisions.
"""

from __future__ import annotations

from typing import Any, Callable

_SINGLE_LAYER_PREFIX = "backbone.model.layer."
_DOUBLE_LAYER_PREFIX = "backbone.model.model.layer."


def _remap_layer_prefix(state_dict: dict[str, Any], source: str, target: str) -> dict[str, Any]:
    if source == target:
        return dict(state_dict)
    remapped: dict[str, Any] = {}
    for key, value in state_dict.items():
        if key.startswith(source):
            key = target + key[len(source) :]
        remapped[key] = value
    return remapped


def remap_relation_state_dict_to_single_model_layer(state_dict: dict[str, Any]) -> dict[str, Any]:
    return _remap_layer_prefix(state_dict, _DOUBLE_LAYER_PREFIX, _SINGLE_LAYER_PREFIX)


def remap_relation_state_dict_to_double_model_layer(state_dict: dict[str, Any]) -> dict[str, Any]:
    return _remap_layer_prefix(state_dict, _SINGLE_LAYER_PREFIX, _DOUBLE_LAYER_PREFIX)


def adapt_checkpoint_for_installed_relsgg(checkpoint: dict[str, Any]) -> dict[str, Any]:
    """Return a checkpoint copy whose weight keys match the installed relsgg tower layout."""

    from relsgg.checkpoint import build_model_from_ckpt  # type: ignore[import-not-found]

    adapters: tuple[Callable[[dict[str, Any]], dict[str, Any]], ...] = (
        lambda sd: sd,
        remap_relation_state_dict_to_single_model_layer,
        remap_relation_state_dict_to_double_model_layer,
    )
    last_error: RuntimeError | None = None
    for adapt_weights in adapters:
        candidate = _copy_checkpoint_with_weights(checkpoint, adapt_weights)
        try:
            build_model_from_ckpt(candidate, strict=True)
            return candidate
        except RuntimeError as exc:
            if "strict load failed" not in str(exc):
                raise
            last_error = exc
    if last_error is not None:
        raise last_error
    return dict(checkpoint)


def _copy_checkpoint_with_weights(
    checkpoint: dict[str, Any],
    adapt_weights: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    copied = dict(checkpoint)
    for weights_key in ("ema_model", "model"):
        weights = copied.get(weights_key)
        if isinstance(weights, dict):
            copied[weights_key] = adapt_weights(weights)
    return copied
