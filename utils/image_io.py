import base64
import io
import os
import tempfile
from typing import Iterable
from urllib.request import urlopen

import numpy as np
import torch
from PIL import Image


def tensor_image_to_pil(image_tensor: torch.Tensor) -> Image.Image:
    tensor = image_tensor.detach().cpu()
    if tensor.ndim == 4:
        tensor = tensor[0]
    if tensor.ndim != 3:
        raise ValueError("expected image tensor with shape [H, W, C] or [1, H, W, C]")

    array = torch.clamp(tensor, 0.0, 1.0).mul(255).byte().numpy()
    return Image.fromarray(array, mode="RGB")


def pil_image_to_tensor(image: Image.Image) -> torch.Tensor:
    rgb_image = image.convert("RGB")
    array = np.asarray(rgb_image).astype("float32") / 255.0
    return torch.from_numpy(array)


def bytes_to_pil_image(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data)) as image:
        return image.convert("RGB")


def base64_to_pil_image(data: str) -> Image.Image:
    if data.startswith("data:image/"):
        _, encoded = data.split(",", 1)
    else:
        encoded = data
    return bytes_to_pil_image(base64.b64decode(encoded))


def pil_image_to_base64(image: Image.Image, output_format: str = "PNG") -> str:
    buffer = io.BytesIO()
    image.save(buffer, format=output_format.upper())
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def resize_pil_image_for_upload(image: Image.Image, max_edge: int = 1536) -> Image.Image:
    rgb_image = image.convert("RGB")
    if max(rgb_image.size) <= max_edge:
        return rgb_image
    resized = rgb_image.copy()
    resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
    resized.thumbnail((max_edge, max_edge), resampling)
    return resized


def pil_image_to_data_url(
    image: Image.Image,
    *,
    output_format: str = "JPEG",
    max_edge: int | None = None,
    quality: int = 85,
) -> str:
    upload_image = resize_pil_image_for_upload(image, max_edge) if max_edge else image.convert("RGB")
    normalized_format = output_format.upper()
    buffer = io.BytesIO()
    save_kwargs = {}
    if normalized_format in {"JPEG", "JPG", "WEBP"}:
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
    upload_image.save(buffer, format=normalized_format, **save_kwargs)
    mime_format = "jpeg" if normalized_format in {"JPEG", "JPG"} else normalized_format.lower()
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/{mime_format};base64,{encoded}"


def load_url_image(url: str, timeout: int = 120) -> Image.Image:
    with urlopen(url, timeout=timeout) as response:
        return bytes_to_pil_image(response.read())


def save_pil_image_to_temp_file(image: Image.Image, suffix: str = ".png") -> str:
    handle, path = tempfile.mkstemp(suffix=suffix)
    os.close(handle)
    image.save(path)
    return path


def batch_tensor_images(images: Iterable[torch.Tensor]) -> torch.Tensor:
    normalized: list[torch.Tensor] = []
    for tensor in images:
        if tensor.ndim == 4:
            normalized.extend(list(tensor))
        else:
            normalized.append(tensor)
    if not normalized:
        raise ValueError("expected at least one image tensor")
    return torch.stack(normalized, dim=0)
