from __future__ import annotations

from typing import Callable

try:
    from .banana_client import BananaClient
    from .image2_client import Image2Client
    from ..utils.errors import (
        NanaixNodeError,
        prompt_required_message,
        reference_image_required_message,
        required_key_message,
        warn_ignored_image2_only_options,
    )
    from ..utils.image_io import batch_tensor_images
    from ..utils.size_mapping import map_banana_size, map_image2_size
except ImportError:  # pragma: no cover - local pytest import fallback
    from services.banana_client import BananaClient
    from services.image2_client import Image2Client
    from utils.errors import (
        NanaixNodeError,
        prompt_required_message,
        reference_image_required_message,
        required_key_message,
        warn_ignored_image2_only_options,
    )
    from utils.image_io import batch_tensor_images
    from utils.size_mapping import map_banana_size, map_image2_size


class NanaixRouter:
    IMAGE2_PREFIX = "gpt-image-"
    BANANA_PREFIX = "nano-banana-"

    def __init__(
        self,
        image2_client_factory: Callable[[str], Image2Client] | None = None,
        banana_client_factory: Callable[[str], BananaClient] | None = None,
    ) -> None:
        self.image2_client_factory = image2_client_factory or Image2Client
        self.banana_client_factory = banana_client_factory or BananaClient

    def run_text(
        self,
        *,
        prompt: str,
        model: str,
        width: int,
        height: int,
        n: int,
        quality: str,
        output_format: str,
        background: str,
        style: str,
        moderation: str,
        output_compression: int,
        partial_images: int,
        stream: bool,
        api_key: str,
    ):
        provider = self._resolve_provider(model, "Nanaix_Text")
        self._validate_prompt(prompt, "Nanaix_Text", model)
        key = self._require_key("Nanaix_Text", model, "api_key", api_key)
        if provider == "image2":
            client = self.image2_client_factory(key)
            images = client.generate(
                node_name="Nanaix_Text",
                prompt=prompt,
                model=model,
                size=map_image2_size(width, height),
                n=n,
                quality=quality,
                output_format=output_format,
                background=background,
                style=style,
                moderation=moderation,
                output_compression=output_compression,
                partial_images=partial_images,
                stream=stream,
            )
            return batch_tensor_images(images)

        warn_ignored_image2_only_options(
            model=model,
            background=background,
            style=style,
            moderation=moderation,
            output_compression=output_compression,
            partial_images=partial_images,
            stream=stream,
        )
        aspect_ratio, image_size = map_banana_size(width, height)
        client = self.banana_client_factory(key)
        images = client.generate(
            node_name="Nanaix_Text",
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            n=n,
            quality=quality,
            output_format=output_format,
        )
        return batch_tensor_images(images)

    def run_image(
        self,
        *,
        prompt: str,
        model: str,
        width: int,
        height: int,
        n: int,
        quality: str,
        output_format: str,
        background: str,
        style: str,
        moderation: str,
        output_compression: int,
        partial_images: int,
        stream: bool,
        api_key: str,
        reference_images: list,
    ):
        provider = self._resolve_provider(model, "Nanaix_Image")
        self._validate_prompt(prompt, "Nanaix_Image", model)
        if not reference_images:
            raise NanaixNodeError(f"Nanaix_Image: {reference_image_required_message()}")

        key = self._require_key("Nanaix_Image", model, "api_key", api_key)
        if provider == "image2":
            client = self.image2_client_factory(key)
            images = client.edit(
                node_name="Nanaix_Image",
                prompt=prompt,
                model=model,
                size=map_image2_size(width, height),
                n=n,
                quality=quality,
                output_format=output_format,
                background=background,
                style=style,
                moderation=moderation,
                output_compression=output_compression,
                partial_images=partial_images,
                stream=stream,
                reference_images=reference_images,
            )
            return batch_tensor_images(images)

        warn_ignored_image2_only_options(
            model=model,
            background=background,
            style=style,
            moderation=moderation,
            output_compression=output_compression,
            partial_images=partial_images,
            stream=stream,
        )
        aspect_ratio, image_size = map_banana_size(width, height)
        client = self.banana_client_factory(key)
        images = client.generate(
            node_name="Nanaix_Image",
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            n=n,
            quality=quality,
            output_format=output_format,
            reference_images=reference_images,
        )
        return batch_tensor_images(images)

    @staticmethod
    def _validate_prompt(prompt: str, node_name: str, model: str) -> None:
        if not prompt.strip():
            raise NanaixNodeError(f"{node_name}: {prompt_required_message(node_name)}")

    @staticmethod
    def _require_key(node_name: str, model: str, field_name: str, value: str) -> str:
        if not value.strip():
            raise NanaixNodeError(f"{node_name}: {required_key_message(model, field_name)}")
        return value

    @classmethod
    def _resolve_provider(cls, model: str, node_name: str) -> str:
        normalized = model.strip()
        if normalized.startswith(cls.IMAGE2_PREFIX):
            return "image2"
        if normalized.startswith(cls.BANANA_PREFIX):
            return "banana"
        raise NanaixNodeError(
            f"{node_name}: unsupported model {model}. "
            f"Use a model name starting with {cls.IMAGE2_PREFIX} or {cls.BANANA_PREFIX}."
        )
