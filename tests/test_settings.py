import json
from pathlib import Path

from config.settings import DEFAULT_CONFIG, load_config, save_config, success_config_payload


def test_load_config_returns_defaults_when_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "missing.json"

    loaded = load_config(config_path)

    assert loaded == DEFAULT_CONFIG


def test_load_config_merges_saved_values(tmp_path: Path) -> None:
    config_path = tmp_path / "saved.json"
    config_path.write_text(json.dumps({"api_key": "shared-key", "width": 2048}), encoding="utf-8")

    loaded = load_config(config_path)

    assert loaded["api_key"] == "shared-key"
    assert loaded["width"] == 2048
    assert loaded["model"] == DEFAULT_CONFIG["model"]


def test_load_config_migrates_legacy_provider_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "saved.json"
    config_path.write_text(
        json.dumps({"banana_api_key": "banana", "model": "nano-banana-pro"}),
        encoding="utf-8",
    )

    loaded = load_config(config_path)

    assert loaded["api_key"] == "banana"
    assert loaded["model"] == "nano-banana-pro"


def test_load_config_ignores_invalid_saved_value_types(tmp_path: Path) -> None:
    config_path = tmp_path / "saved.json"
    config_path.write_text(
        json.dumps(
            {
                "api_key": 123,
                "model": {"bad": "value"},
                "width": "1536",
                "height": None,
                "n": "2",
                "partial_images": "4",
                "stream": "true",
                "output_compression": "25",
            }
        ),
        encoding="utf-8",
    )

    loaded = load_config(config_path)

    assert loaded["api_key"] == DEFAULT_CONFIG["api_key"]
    assert loaded["model"] == DEFAULT_CONFIG["model"]
    assert loaded["width"] == 1536
    assert loaded["height"] == DEFAULT_CONFIG["height"]
    assert loaded["n"] == 2
    assert loaded["partial_images"] == 4
    assert loaded["stream"] is True
    assert loaded["output_compression"] == 25


def test_load_config_keeps_free_form_model_values(tmp_path: Path) -> None:
    config_path = tmp_path / "saved.json"
    config_path.write_text(
        json.dumps(
            {
                "model": "gpt-image-2-experimental",
                "resolution_preset": "ultra_wide_8k",
                "quality": "ultra",
                "output_format": "bmp",
                "background": "checkerboard",
                "style": "cinematic",
                "moderation": "strict",
            }
        ),
        encoding="utf-8",
    )

    loaded = load_config(config_path)

    assert loaded["model"] == "gpt-image-2-experimental"
    assert loaded["resolution_preset"] == DEFAULT_CONFIG["resolution_preset"]
    assert loaded["quality"] == DEFAULT_CONFIG["quality"]
    assert loaded["output_format"] == DEFAULT_CONFIG["output_format"]
    assert loaded["background"] == DEFAULT_CONFIG["background"]
    assert loaded["style"] == DEFAULT_CONFIG["style"]
    assert loaded["moderation"] == DEFAULT_CONFIG["moderation"]


def test_success_config_payload_keeps_supported_fields_only() -> None:
    payload = success_config_payload(
        {
            "api_key": "shared-key",
            "model": "nano-banana-pro",
            "resolution_preset": "portrait_hd",
            "background": "transparent",
            "style": "vivid",
            "moderation": "auto",
            "output_compression": 65,
            "partial_images": 3,
            "stream": True,
            "extra": "ignore",
        }
    )

    assert payload["api_key"] == "shared-key"
    assert payload["model"] == "nano-banana-pro"
    assert payload["resolution_preset"] == "portrait_hd"
    assert payload["background"] == "transparent"
    assert payload["style"] == "vivid"
    assert payload["moderation"] == "auto"
    assert payload["output_compression"] == 65
    assert payload["partial_images"] == 3
    assert payload["stream"] is True
    assert "extra" not in payload


def test_save_config_writes_payload(tmp_path: Path) -> None:
    config_path = tmp_path / "saved.json"

    save_config({"api_key": "shared-key", "n": 2, "partial_images": 4, "stream": True}, config_path)

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["api_key"] == "shared-key"
    assert saved["n"] == 2
    assert saved["partial_images"] == 4
    assert saved["stream"] is True
    assert saved["model"] == DEFAULT_CONFIG["model"]
