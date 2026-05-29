import json
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = {
    "api_key": "",
    "model": "gpt-image-2",
    "resolution_preset": "custom",
    "width": 1024,
    "height": 1024,
    "n": 1,
    "quality": "high",
    "output_format": "png",
    "background": "auto",
    "style": "natural",
    "moderation": "auto",
    "output_compression": 0,
    "partial_images": 0,
    "stream": False,
}

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "nanaix_config.json"

CONFIG_ALLOWED_VALUES = {
    "resolution_preset": {
        "custom",
        "square",
        "square_2k",
        "square_4k",
        "landscape_hd",
        "portrait_hd",
        "landscape_2k",
        "portrait_2k",
        "landscape_4k",
        "portrait_4k",
    },
    "quality": {"high", "medium", "low"},
    "output_format": {"png", "webp", "jpeg"},
    "background": {"auto", "transparent"},
    "style": {"natural", "vivid"},
    "moderation": {"auto", "low"},
}

LEGACY_KEY_FIELDS = ("image2_api_key", "banana_api_key")


def _coerce_config_value(key: str, value: Any) -> Any:
    default = DEFAULT_CONFIG[key]

    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
        return default

    if isinstance(default, int):
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return default
            try:
                return int(text)
            except ValueError:
                return default
        return default

    if isinstance(default, str):
        if isinstance(value, str):
            allowed_values = CONFIG_ALLOWED_VALUES.get(key)
            if allowed_values is not None and value not in allowed_values:
                return default
            return value
        return default

    return value if isinstance(value, type(default)) else default


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return deepcopy(DEFAULT_CONFIG)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULT_CONFIG)

    merged = deepcopy(DEFAULT_CONFIG)
    for key in merged:
        if key in raw:
            merged[key] = _coerce_config_value(key, raw[key])
    if not merged["api_key"]:
        legacy_model = raw.get("model")
        if isinstance(legacy_model, str) and legacy_model.startswith("nano-banana-"):
            legacy_candidates = ("banana_api_key", "image2_api_key")
        elif isinstance(legacy_model, str) and legacy_model.startswith("gpt-image-"):
            legacy_candidates = ("image2_api_key", "banana_api_key")
        else:
            legacy_candidates = LEGACY_KEY_FIELDS
        for legacy_key in legacy_candidates:
            if legacy_key in raw:
                coerced = _coerce_config_value("api_key", raw[legacy_key])
                if isinstance(coerced, str) and coerced.strip():
                    merged["api_key"] = coerced
                    break
    return merged


def success_config_payload(values: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(DEFAULT_CONFIG)
    if "api_key" not in values:
        for legacy_key in LEGACY_KEY_FIELDS:
            legacy_value = values.get(legacy_key)
            if isinstance(legacy_value, str) and legacy_value.strip():
                values = dict(values)
                values["api_key"] = legacy_value
                break
    for key in payload:
        if key in values:
            payload[key] = _coerce_config_value(key, values[key])
    return payload


def save_config(values: dict[str, Any], config_path: Path | None = None) -> Path:
    path = config_path or DEFAULT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = success_config_payload(values)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return path
