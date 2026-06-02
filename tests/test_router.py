from __future__ import annotations

from typing import Any

import pytest
import torch

from services.router import NanaixRouter
from utils.errors import NanaixNodeError


class RecordingImage2Client:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def generate(self, **kwargs: Any) -> list[torch.Tensor]:
        self.calls.append(("generate", kwargs))
        return [torch.zeros((4, 4, 3), dtype=torch.float32)]

    def edit(self, **kwargs: Any) -> list[torch.Tensor]:
        self.calls.append(("edit", kwargs))
        return [torch.ones((4, 4, 3), dtype=torch.float32)]


class RecordingBananaClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate(self, **kwargs: Any) -> list[torch.Tensor]:
        self.calls.append(kwargs)
        return [torch.ones((4, 4, 3), dtype=torch.float32) for _ in range(kwargs["n"])]


def test_router_uses_image2_generate_for_gpt_image_family() -> None:
    image2 = RecordingImage2Client()
    banana = RecordingBananaClient()
    router = NanaixRouter(image2_client_factory=lambda _: image2, banana_client_factory=lambda _: banana)

    result = router.run_text(
        prompt="hello",
        model="gpt-image-2-experimental",
        width=1024,
        height=1024,
        n=1,
        quality="high",
        output_format="png",
        background="transparent",
        style="vivid",
        moderation="auto",
        output_compression=55,
        partial_images=2,
        stream=True,
        api_key="image-key",
    )

    assert result.shape == (1, 4, 4, 3)
    assert image2.calls[0][0] == "generate"
    assert image2.calls[0][1]["model"] == "gpt-image-2-experimental"
    assert image2.calls[0][1]["size"] == "1024x1024"
    assert image2.calls[0][1]["background"] == "transparent"
    assert image2.calls[0][1]["style"] == "vivid"
    assert image2.calls[0][1]["moderation"] == "auto"
    assert image2.calls[0][1]["output_compression"] == 55
    assert image2.calls[0][1]["partial_images"] == 2
    assert image2.calls[0][1]["stream"] is True
    assert not banana.calls


def test_router_uses_banana_generate_for_banana_family() -> None:
    image2 = RecordingImage2Client()
    banana = RecordingBananaClient()
    router = NanaixRouter(image2_client_factory=lambda _: image2, banana_client_factory=lambda _: banana)

    result = router.run_text(
        prompt="hello",
        model="nano-banana-pro-v2",
        width=2048,
        height=1024,
        n=2,
        quality="high",
        output_format="png",
        background="auto",
        style="natural",
        moderation="auto",
        output_compression=0,
        partial_images=0,
        stream=True,
        api_key="banana-key",
    )

    assert result.shape == (2, 4, 4, 3)
    assert banana.calls[0]["model"] == "nano-banana-pro-v2"
    assert banana.calls[0]["aspect_ratio"] == "2:1"
    assert banana.calls[0]["image_size"] == "2K"
    assert "background" not in banana.calls[0]
    assert "style" not in banana.calls[0]
    assert "moderation" not in banana.calls[0]
    assert "output_compression" not in banana.calls[0]
    assert "partial_images" not in banana.calls[0]
    assert "stream" not in banana.calls[0]
    assert not image2.calls


def test_router_warns_when_banana_ignores_image2_only_options() -> None:
    image2 = RecordingImage2Client()
    banana = RecordingBananaClient()
    router = NanaixRouter(image2_client_factory=lambda _: image2, banana_client_factory=lambda _: banana)

    with pytest.warns(UserWarning, match="ignored for nano-banana-pro"):
        result = router.run_text(
            prompt="hello",
            model="nano-banana-pro",
            width=2048,
            height=1024,
            n=1,
            quality="high",
            output_format="png",
            background="transparent",
            style="vivid",
            moderation="low",
            output_compression=35,
            partial_images=3,
            stream=True,
            api_key="banana-key",
        )

    assert result.shape == (1, 4, 4, 3)
    assert not image2.calls


def test_router_creates_clients_with_current_api_key_for_each_call() -> None:
    image2_keys: list[str] = []
    banana_keys: list[str] = []
    image2 = RecordingImage2Client()
    banana = RecordingBananaClient()
    router = NanaixRouter(
        image2_client_factory=lambda api_key: image2_keys.append(api_key) or image2,
        banana_client_factory=lambda api_key: banana_keys.append(api_key) or banana,
    )

    router.run_text(
        prompt="banana first",
        model="nano-banana-2",
        width=1024,
        height=1024,
        n=1,
        quality="high",
        output_format="png",
        background="auto",
        style="natural",
        moderation="auto",
        output_compression=0,
        partial_images=0,
        stream=False,
        api_key="banana-key",
    )
    router.run_text(
        prompt="image2 second",
        model="gpt-image-2",
        width=1024,
        height=1024,
        n=1,
        quality="high",
        output_format="png",
        background="auto",
        style="natural",
        moderation="auto",
        output_compression=0,
        partial_images=0,
        stream=False,
        api_key="image-key",
    )

    assert banana_keys == ["banana-key"]
    assert image2_keys == ["image-key"]
    assert banana.calls[0]["model"] == "nano-banana-2"
    assert image2.calls[0][1]["model"] == "gpt-image-2"


def test_router_requires_api_key_for_supported_model_family() -> None:
    router = NanaixRouter(
        image2_client_factory=lambda _: RecordingImage2Client(),
        banana_client_factory=lambda _: RecordingBananaClient(),
    )

    with pytest.raises(NanaixNodeError) as error:
        router.run_text(
            prompt="hello",
            model="nano-banana-2",
            width=1024,
            height=1024,
            n=1,
            quality="high",
            output_format="png",
            background="auto",
            style="natural",
            moderation="auto",
            output_compression=0,
            partial_images=0,
            stream=False,
            api_key="",
        )

    assert (
        str(error.value)
        == "Nanaix_Text: nano-banana-2 requires api_key. Paste your nano-banana key into the node. Saved config only pre-fills new nodes; a blank visible key is still treated as missing."
    )


def test_router_requires_reference_images_for_image_node() -> None:
    router = NanaixRouter(
        image2_client_factory=lambda _: RecordingImage2Client(),
        banana_client_factory=lambda _: RecordingBananaClient(),
    )

    with pytest.raises(NanaixNodeError) as error:
        router.run_image(
            prompt="hello",
            model="gpt-image-2",
            width=1024,
            height=1024,
            n=1,
            quality="high",
            output_format="png",
            background="auto",
            style="natural",
            moderation="auto",
            output_compression=0,
            partial_images=0,
            stream=False,
            api_key="image-key",
            reference_images=[],
        )

    assert (
        str(error.value)
        == "Nanaix_Image: At least one reference image is required. Connect image_1 or another IMAGE input before queueing Nanaix_Image."
    )


def test_router_rejects_unsupported_model_family() -> None:
    router = NanaixRouter(
        image2_client_factory=lambda _: RecordingImage2Client(),
        banana_client_factory=lambda _: RecordingBananaClient(),
    )

    with pytest.raises(NanaixNodeError) as error:
        router.run_text(
            prompt="hello",
            model="unknown-model",
            width=1024,
            height=1024,
            n=1,
            quality="high",
            output_format="png",
            background="auto",
            style="natural",
            moderation="auto",
            output_compression=0,
            partial_images=0,
            stream=False,
            api_key="shared-key",
        )

    assert "unsupported model unknown-model" in str(error.value)
    assert "gpt-image-" in str(error.value)
    assert "nano-banana-" in str(error.value)
