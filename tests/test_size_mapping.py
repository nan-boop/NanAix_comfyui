import pytest

from utils.size_mapping import apply_resolution_preset, map_banana_size, map_image2_size


def test_map_image2_size_prefers_square() -> None:
    assert map_image2_size(1024, 1024) == "1024x1024"


def test_map_image2_size_prefers_landscape() -> None:
    assert map_image2_size(2048, 1024) == "1536x1024"


def test_map_image2_size_preserves_supported_custom_square_size() -> None:
    assert map_image2_size(2048, 2048) == "2048x2048"


def test_map_image2_size_preserves_supported_custom_landscape_size() -> None:
    assert map_image2_size(2048, 1536) == "2048x1536"


def test_map_image2_size_preserves_supported_custom_portrait_size() -> None:
    assert map_image2_size(1536, 2048) == "1536x2048"


def test_map_banana_size_uses_reduced_aspect_ratio_and_size_bucket() -> None:
    assert map_banana_size(2048, 1024) == ("2:1", "2K")


def test_size_mapping_rejects_non_positive_values() -> None:
    with pytest.raises(ValueError):
        map_image2_size(0, 512)

    with pytest.raises(ValueError):
        map_banana_size(-1, 512)


def test_apply_resolution_preset_returns_custom_dimensions_unchanged() -> None:
    assert apply_resolution_preset("custom", 1400, 900) == (1400, 900)


def test_apply_resolution_preset_overrides_dimensions_for_known_preset() -> None:
    assert apply_resolution_preset("landscape_hd", 1, 1) == (1536, 1024)
    assert apply_resolution_preset("square_2k", 1, 1) == (2048, 2048)
    assert apply_resolution_preset("square_4k", 1, 1) == (4096, 4096)
    assert apply_resolution_preset("landscape_4k", 1, 1) == (4096, 3072)
    assert apply_resolution_preset("portrait_4k", 1, 1) == (3072, 4096)


def test_apply_resolution_preset_rejects_unknown_preset() -> None:
    with pytest.raises(ValueError):
        apply_resolution_preset("not-a-preset", 1024, 1024)
