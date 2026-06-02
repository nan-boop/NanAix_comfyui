from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
import torch

from config.settings import save_config
from nodes.nanaix_image import NanaixImageNode
from nodes.nanaix_text import NanaixTextNode
from services.router import NanaixRouter


class SuccessfulRouter(NanaixRouter):
    def __init__(self) -> None:
        super().__init__()
        self.last_payload = None

    def run_text(self, **kwargs):  # type: ignore[override]
        self.last_payload = kwargs
        return torch.zeros((1, 4, 4, 3), dtype=torch.float32)

    def run_image(self, **kwargs):  # type: ignore[override]
        self.last_payload = kwargs
        return torch.ones((2, 4, 4, 3), dtype=torch.float32)


class FailingRouter(NanaixRouter):
    def run_text(self, **kwargs):  # type: ignore[override]
        raise RuntimeError("simulated generation failure")

    def run_image(self, **kwargs):  # type: ignore[override]
        raise RuntimeError("simulated generation failure")


def text_payload(*, prompt: str = "hello", model: str = "gpt-image-2", api_key: str = "image-key") -> dict[str, object]:
    return {
        "prompt": prompt,
        "model": model,
        "resolution_preset": "custom",
        "width": 1024,
        "height": 1024,
        "n": 1,
        "quality": "high",
        "output_format": "png",
        "background": "transparent",
        "style": "vivid",
        "moderation": "auto",
        "output_compression": 60,
        "partial_images": 3,
        "stream": True,
        "api_key": api_key,
        "official_website": "https://ai.nanaix.com",
        "prompt_graph": {"1": {"class_type": "Nanaix_Text"}},
        "future_display_only_field": "kept out of router payload",
    }


def image_payload(*, prompt: str = "edit", model: str = "gpt-image-2", api_key: str = "image-key") -> dict[str, object]:
    payload = text_payload(prompt=prompt, model=model, api_key=api_key)
    payload["background"] = "auto"
    payload["style"] = "natural"
    payload["moderation"] = "low"
    return payload


def test_text_node_input_defaults_reflect_saved_config(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "nanaix_config.json"
    save_config({"api_key": "saved-key", "width": 2048, "partial_images": 2, "stream": True}, config_path)
    monkeypatch.setattr("config.settings.DEFAULT_CONFIG_PATH", config_path)

    input_types = NanaixTextNode.INPUT_TYPES()

    assert input_types["required"]["api_key"][1]["default"] == "saved-key"
    assert input_types["required"]["width"][1]["default"] == 2048
    assert input_types["required"]["partial_images"][1]["default"] == 2
    assert input_types["required"]["stream"][1]["default"] is True


def test_image_node_input_defaults_reflect_saved_config(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "nanaix_config.json"
    save_config({"api_key": "saved-key", "height": 1536, "quality": "medium"}, config_path)
    monkeypatch.setattr("config.settings.DEFAULT_CONFIG_PATH", config_path)

    input_types = NanaixImageNode.INPUT_TYPES()

    assert input_types["required"]["api_key"][1]["default"] == "saved-key"
    assert input_types["required"]["height"][1]["default"] == 1536
    assert input_types["required"]["quality"][1]["default"] == "medium"


def test_text_node_input_metadata_includes_placeholders() -> None:
    input_types = NanaixTextNode.INPUT_TYPES()

    assert input_types["required"]["prompt"][1]["placeholder"]
    assert input_types["required"]["model"][1]["placeholder"]
    assert input_types["required"]["api_key"][1]["placeholder"]
    assert input_types["required"]["official_website"][1]["default"] == "https://ai.nanaix.com"


def test_text_node_input_metadata_includes_tooltips() -> None:
    required = NanaixTextNode.INPUT_TYPES()["required"]

    assert "gpt-image-*" in required["model"][1]["tooltip"]
    assert "transparent background" in required["model"][1]["tooltip"].lower()
    assert "nano-banana-*" in required["model"][1]["tooltip"]
    assert "single api_key field" in required["model"][1]["tooltip"].lower()
    assert "resolution preset" in required["resolution_preset"][1]["tooltip"].lower()
    assert "requested output width" in required["width"][1]["tooltip"].lower()
    assert "number of images" in required["n"][1]["tooltip"].lower()
    assert "image batch" in required["n"][1]["tooltip"].lower()
    assert "previewimage" in required["n"][1]["tooltip"].lower()
    assert "saveimage" in required["n"][1]["tooltip"].lower()
    assert "transparent" in required["background"][1]["tooltip"].lower()
    assert "vivid" in required["style"][1]["tooltip"].lower()
    assert "moderation" in required["moderation"][1]["tooltip"].lower()
    assert "compression" in required["output_compression"][1]["tooltip"].lower()
    assert "streamed preview" in required["partial_images"][1]["tooltip"].lower()
    assert "sse" in required["stream"][1]["tooltip"].lower()
    assert "single api key field" in required["api_key"][1]["tooltip"].lower()
    assert "official website" in required["official_website"][1]["tooltip"].lower()
    assert "square_2k" in required["resolution_preset"][0]
    assert "square_4k" in required["resolution_preset"][0]
    assert "landscape_4k" in required["resolution_preset"][0]
    assert "portrait_4k" in required["resolution_preset"][0]


def test_text_node_description_summarizes_runtime_contract() -> None:
    description = NanaixTextNode.DESCRIPTION

    assert "ComfyUI-native IMAGE output" in description
    assert "n > 1" in description
    assert "PreviewImage" in description
    assert "SaveImage" in description
    assert "saved local config" in description
    assert "empty visible key still raises an error" in description


def test_text_node_validate_inputs_checks_required_fields() -> None:
    input_types = NanaixTextNode.INPUT_TYPES()

    assert input_types["hidden"]["prompt_graph"] == "PROMPT"
    assert inspect.getfullargspec(NanaixTextNode.VALIDATE_INPUTS).args == ["cls", "prompt_graph"]
    assert (
        NanaixTextNode.VALIDATE_INPUTS(
            prompt_graph={"1": {"class_type": "Nanaix_Text", "inputs": {"prompt": "", "model": "gpt-image-2", "api_key": "image-key"}}}
        )
        == "prompt is required. Describe the image you want Nanaix to generate."
    )
    assert (
        NanaixTextNode.VALIDATE_INPUTS(
            prompt_graph={"1": {"class_type": "Nanaix_Text", "inputs": {"prompt": "hello", "model": "", "api_key": "image-key"}}}
        )
        == "model is required. Enter a Nanaix model name such as gpt-image-2 or nano-banana-pro."
    )
    assert (
        NanaixTextNode.VALIDATE_INPUTS(
            prompt_graph={"1": {"class_type": "Nanaix_Text", "inputs": {"prompt": "hello", "model": "weird-model", "api_key": "image-key"}}}
        )
        == "unsupported model weird-model. Use a model name starting with gpt-image- or nano-banana-."
    )
    assert (
        NanaixTextNode.VALIDATE_INPUTS(
            prompt_graph={"1": {"class_type": "Nanaix_Text", "inputs": {"prompt": "hello", "model": "gpt-image-2", "api_key": ""}}}
        )
        == "gpt-image-2 requires api_key. Paste your image-2 key into the node. Saved config only pre-fills new nodes; a blank visible key is still treated as missing."
    )
    assert (
        NanaixTextNode.VALIDATE_INPUTS(
            prompt_graph={"1": {"class_type": "Nanaix_Text", "inputs": {"prompt": "hello", "model": "nano-banana-pro", "api_key": ""}}}
        )
        == "nano-banana-pro requires api_key. Paste your nano-banana key into the node. Saved config only pre-fills new nodes; a blank visible key is still treated as missing."
    )
    assert (
        NanaixTextNode.VALIDATE_INPUTS(
            prompt_graph={"1": {"class_type": "Nanaix_Text", "inputs": {"prompt": "hello", "model": "gpt-image-2", "api_key": "image-key"}}}
        )
        is True
    )


def test_text_node_returns_router_image_and_saves_config(tmp_path: Path) -> None:
    config_path = tmp_path / "nanaix_config.json"
    router = SuccessfulRouter()
    node = NanaixTextNode(router=router, config_path=config_path)

    result = node.generate(**text_payload())

    assert result[0].shape == (1, 4, 4, 3)
    assert router.last_payload["api_key"] == "image-key"
    assert "official_website" not in router.last_payload
    assert "prompt_graph" not in router.last_payload
    assert "future_display_only_field" not in router.last_payload
    assert config_path.exists()
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["api_key"] == "image-key"
    assert saved["model"] == "gpt-image-2"


def test_text_node_uses_trimmed_visible_api_key_instead_of_saved_config(tmp_path: Path) -> None:
    config_path = tmp_path / "nanaix_config.json"
    save_config({"api_key": "banana-key", "model": "nano-banana-2"}, config_path)
    router = SuccessfulRouter()
    node = NanaixTextNode(router=router, config_path=config_path)

    result = node.generate(**text_payload(model="gpt-image-2", api_key="  image-key  "))

    assert result[0].shape == (1, 4, 4, 3)
    assert router.last_payload["model"] == "gpt-image-2"
    assert router.last_payload["api_key"] == "image-key"
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["api_key"] == "image-key"
    assert saved["model"] == "gpt-image-2"


def test_text_node_does_not_save_config_when_generation_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "nanaix_config.json"
    save_config({"api_key": "banana-key", "model": "nano-banana-2"}, config_path)
    node = NanaixTextNode(router=FailingRouter(), config_path=config_path)

    with pytest.raises(RuntimeError, match="simulated generation failure"):
        node.generate(**text_payload(model="gpt-image-2", api_key="image-key"))

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["api_key"] == "banana-key"
    assert saved["model"] == "nano-banana-2"


def test_text_node_resolution_preset_overrides_width_and_height(tmp_path: Path) -> None:
    router = SuccessfulRouter()
    node = NanaixTextNode(router=router, config_path=tmp_path / "nanaix_config.json")

    payload = text_payload()
    payload["resolution_preset"] = "landscape_hd"
    payload["width"] = 512
    payload["height"] = 512
    node.generate(**payload)

    assert router.last_payload["width"] == 1536
    assert router.last_payload["height"] == 1024
    assert "resolution_preset" not in router.last_payload


def test_text_node_4k_resolution_preset_overrides_width_and_height(tmp_path: Path) -> None:
    router = SuccessfulRouter()
    node = NanaixTextNode(router=router, config_path=tmp_path / "nanaix_config.json")

    payload = text_payload()
    payload["resolution_preset"] = "landscape_4k"
    payload["width"] = 512
    payload["height"] = 512
    payload["stream"] = False
    payload["partial_images"] = 0
    node.generate(**payload)

    assert router.last_payload["width"] == 4096
    assert router.last_payload["height"] == 3072


def test_text_node_square_4k_resolution_preset_overrides_width_and_height(tmp_path: Path) -> None:
    router = SuccessfulRouter()
    node = NanaixTextNode(router=router, config_path=tmp_path / "nanaix_config.json")

    payload = text_payload()
    payload["resolution_preset"] = "square_4k"
    payload["width"] = 512
    payload["height"] = 256
    node.generate(**payload)

    assert router.last_payload["width"] == 4096
    assert router.last_payload["height"] == 4096


def test_image_node_collects_optional_images_and_saves_config(tmp_path: Path) -> None:
    config_path = tmp_path / "nanaix_config.json"
    router = SuccessfulRouter()
    node = NanaixImageNode(router=router, config_path=config_path)

    image_a = torch.zeros((4, 4, 3), dtype=torch.float32)
    image_b = torch.ones((4, 4, 3), dtype=torch.float32)
    payload = image_payload()
    payload["image_1"] = image_a
    payload["image_3"] = image_b
    result = node.generate(**payload)

    assert result[0].shape == (2, 4, 4, 3)
    assert router.last_payload["reference_images"] == [image_a, image_b]
    assert "image_1" not in router.last_payload
    assert "image_3" not in router.last_payload
    assert "official_website" not in router.last_payload
    assert "prompt_graph" not in router.last_payload
    assert "future_display_only_field" not in router.last_payload
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["api_key"] == "image-key"
    assert saved["model"] == "gpt-image-2"


def test_image_node_uses_trimmed_visible_api_key_instead_of_saved_config(tmp_path: Path) -> None:
    config_path = tmp_path / "nanaix_config.json"
    save_config({"api_key": "banana-key", "model": "nano-banana-2"}, config_path)
    router = SuccessfulRouter()
    node = NanaixImageNode(router=router, config_path=config_path)
    payload = image_payload(model="gpt-image-2", api_key="  image-key  ")
    payload["image_1"] = torch.zeros((4, 4, 3), dtype=torch.float32)

    result = node.generate(**payload)

    assert result[0].shape == (2, 4, 4, 3)
    assert router.last_payload["model"] == "gpt-image-2"
    assert router.last_payload["api_key"] == "image-key"
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["api_key"] == "image-key"
    assert saved["model"] == "gpt-image-2"


def test_image_node_does_not_save_config_when_generation_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "nanaix_config.json"
    save_config({"api_key": "banana-key", "model": "nano-banana-2"}, config_path)
    node = NanaixImageNode(router=FailingRouter(), config_path=config_path)
    payload = image_payload(model="gpt-image-2", api_key="image-key")
    payload["image_1"] = torch.zeros((4, 4, 3), dtype=torch.float32)

    with pytest.raises(RuntimeError, match="simulated generation failure"):
        node.generate(**payload)

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["api_key"] == "banana-key"
    assert saved["model"] == "nano-banana-2"


def test_image_node_validate_inputs_checks_required_fields() -> None:
    input_types = NanaixImageNode.INPUT_TYPES()

    assert input_types["hidden"]["prompt_graph"] == "PROMPT"
    assert inspect.getfullargspec(NanaixImageNode.VALIDATE_INPUTS).args == ["cls", "prompt_graph"]
    assert (
        NanaixImageNode.VALIDATE_INPUTS(
            prompt_graph={"1": {"class_type": "Nanaix_Image", "inputs": {"prompt": "", "model": "gpt-image-2", "api_key": "image-key", "image_1": ["0", 0]}}}
        )
        == "prompt is required. Describe how Nanaix should change the reference image."
    )
    assert (
        NanaixImageNode.VALIDATE_INPUTS(
            prompt_graph={"1": {"class_type": "Nanaix_Image", "inputs": {"prompt": "edit", "model": "", "api_key": "image-key", "image_1": ["0", 0]}}}
        )
        == "model is required. Enter a Nanaix model name such as gpt-image-2 or nano-banana-pro."
    )
    assert (
        NanaixImageNode.VALIDATE_INPUTS(
            prompt_graph={"1": {"class_type": "Nanaix_Image", "inputs": {"prompt": "edit", "model": "weird-model", "api_key": "image-key", "image_1": ["0", 0]}}}
        )
        == "unsupported model weird-model. Use a model name starting with gpt-image- or nano-banana-."
    )
    assert (
        NanaixImageNode.VALIDATE_INPUTS(
            prompt_graph={"1": {"class_type": "Nanaix_Image", "inputs": {"prompt": "edit", "model": "gpt-image-2", "api_key": "", "image_1": ["0", 0]}}}
        )
        == "gpt-image-2 requires api_key. Paste your image-2 key into the node. Saved config only pre-fills new nodes; a blank visible key is still treated as missing."
    )
    assert (
        NanaixImageNode.VALIDATE_INPUTS(
            prompt_graph={"1": {"class_type": "Nanaix_Image", "inputs": {"prompt": "edit", "model": "gpt-image-2", "api_key": "image-key"}}}
        )
        == "At least one reference image is required. Connect image_1 or another IMAGE input before queueing Nanaix_Image."
    )
    assert (
        NanaixImageNode.VALIDATE_INPUTS(
            prompt_graph={"1": {"class_type": "Nanaix_Image", "inputs": {"prompt": "edit", "model": "gpt-image-2", "api_key": "image-key", "image_1": ["0", 0]}}}
        )
        is True
    )


def test_image_node_input_metadata_includes_tooltips() -> None:
    input_types = NanaixImageNode.INPUT_TYPES()
    required = input_types["required"]
    optional = input_types["optional"]

    assert "gpt-image-*" in required["model"][1]["tooltip"]
    assert "transparent background" in required["model"][1]["tooltip"].lower()
    assert "nano-banana-*" in required["model"][1]["tooltip"]
    assert "single api_key field" in required["model"][1]["tooltip"].lower()
    assert "resolution preset" in required["resolution_preset"][1]["tooltip"].lower()
    assert "requested output width" in required["width"][1]["tooltip"].lower()
    assert "number of images" in required["n"][1]["tooltip"].lower()
    assert "previewimage" in required["n"][1]["tooltip"].lower()
    assert "saveimage" in required["n"][1]["tooltip"].lower()
    assert "transparent" in required["background"][1]["tooltip"].lower()
    assert "vivid" in required["style"][1]["tooltip"].lower()
    assert "moderation" in required["moderation"][1]["tooltip"].lower()
    assert "compression" in required["output_compression"][1]["tooltip"].lower()
    assert "streamed preview" in required["partial_images"][1]["tooltip"].lower()
    assert "sse" in required["stream"][1]["tooltip"].lower()
    assert "single api key field" in required["api_key"][1]["tooltip"].lower()
    assert required["official_website"][1]["default"] == "https://ai.nanaix.com"
    assert "official website" in required["official_website"][1]["tooltip"].lower()
    assert len(optional) == 8
    assert "main subject or composition guide" in optional["image_1"][1]["tooltip"].lower()
    assert "secondary style or environment guide" in optional["image_2"][1]["tooltip"].lower()


def test_image_node_description_summarizes_reference_image_behavior() -> None:
    description = NanaixImageNode.DESCRIPTION

    assert "up to 8 reference IMAGE inputs" in description
    assert "ComfyUI-native IMAGE output" in description
    assert "image_1" in description
    assert "image_2" in description
    assert "batched reference input is expanded" in description
    assert "saved local config" in description


def test_image_node_flattens_batched_reference_inputs(tmp_path: Path) -> None:
    router = SuccessfulRouter()
    node = NanaixImageNode(router=router, config_path=tmp_path / "nanaix_config.json")

    batch = torch.stack(
        [
            torch.zeros((4, 4, 3), dtype=torch.float32),
            torch.ones((4, 4, 3), dtype=torch.float32),
        ],
        dim=0,
    )
    payload = image_payload()
    payload["image_1"] = batch
    node.generate(**payload)

    assert len(router.last_payload["reference_images"]) == 2
    assert all(image.shape == (4, 4, 3) for image in router.last_payload["reference_images"])


def test_image_node_resolution_preset_overrides_width_and_height(tmp_path: Path) -> None:
    router = SuccessfulRouter()
    node = NanaixImageNode(router=router, config_path=tmp_path / "nanaix_config.json")

    payload = image_payload()
    payload["resolution_preset"] = "portrait_hd"
    payload["width"] = 512
    payload["height"] = 512
    payload["image_1"] = torch.zeros((4, 4, 3), dtype=torch.float32)
    node.generate(**payload)

    assert router.last_payload["width"] == 1024
    assert router.last_payload["height"] == 1536
    assert "resolution_preset" not in router.last_payload


def test_image_node_4k_resolution_preset_overrides_width_and_height(tmp_path: Path) -> None:
    router = SuccessfulRouter()
    node = NanaixImageNode(router=router, config_path=tmp_path / "nanaix_config.json")

    payload = image_payload()
    payload["resolution_preset"] = "portrait_4k"
    payload["width"] = 512
    payload["height"] = 512
    payload["image_1"] = torch.zeros((4, 4, 3), dtype=torch.float32)
    node.generate(**payload)

    assert router.last_payload["width"] == 3072
    assert router.last_payload["height"] == 4096


def test_image_node_square_2k_resolution_preset_overrides_width_and_height(tmp_path: Path) -> None:
    router = SuccessfulRouter()
    node = NanaixImageNode(router=router, config_path=tmp_path / "nanaix_config.json")

    payload = image_payload()
    payload["resolution_preset"] = "square_2k"
    payload["width"] = 512
    payload["height"] = 256
    payload["image_1"] = torch.zeros((4, 4, 3), dtype=torch.float32)
    node.generate(**payload)

    assert router.last_payload["width"] == 2048
    assert router.last_payload["height"] == 2048
