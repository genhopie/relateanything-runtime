from relateanything_runtime.pipeline.relsgg_checkpoint import (
    remap_relation_state_dict_to_double_model_layer,
    remap_relation_state_dict_to_single_model_layer,
)


def test_remap_relation_layer_prefix_to_single() -> None:
    source = {
        "backbone.model.model.layer.0.norm1.weight": 1,
        "backbone.model.embeddings.cls_token": 2,
    }
    remapped = remap_relation_state_dict_to_single_model_layer(source)
    assert remapped["backbone.model.layer.0.norm1.weight"] == 1
    assert remapped["backbone.model.embeddings.cls_token"] == 2


def test_remap_relation_layer_prefix_to_double() -> None:
    source = {
        "backbone.model.layer.0.norm1.weight": 1,
        "backbone.model.embeddings.cls_token": 2,
    }
    remapped = remap_relation_state_dict_to_double_model_layer(source)
    assert remapped["backbone.model.model.layer.0.norm1.weight"] == 1
    assert remapped["backbone.model.embeddings.cls_token"] == 2
