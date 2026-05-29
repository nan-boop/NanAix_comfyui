import base64
import io

import torch
from PIL import Image

from utils.image_io import (
    base64_to_pil_image,
    batch_tensor_images,
    pil_image_to_base64,
    pil_image_to_tensor,
    tensor_image_to_pil,
)


def make_image(color: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGB", (4, 4), color)


def test_tensor_round_trip_preserves_shape() -> None:
    image = make_image((255, 0, 0))

    tensor = pil_image_to_tensor(image)
    rebuilt = tensor_image_to_pil(tensor)

    assert tensor.shape == (4, 4, 3)
    assert rebuilt.size == (4, 4)


def test_base64_to_pil_image_decodes_png() -> None:
    image = make_image((0, 255, 0))
    raw = pil_image_to_base64(image)

    decoded = base64_to_pil_image(raw)

    assert decoded.size == (4, 4)


def test_base64_to_pil_image_decodes_data_url() -> None:
    image = make_image((0, 0, 255))
    raw = pil_image_to_base64(image)
    data_url = f"data:image/png;base64,{raw}"

    decoded = base64_to_pil_image(data_url)

    assert decoded.getpixel((0, 0)) == (0, 0, 255)


def test_batch_tensor_images_stacks_single_images() -> None:
    image_a = pil_image_to_tensor(make_image((255, 0, 0)))
    image_b = pil_image_to_tensor(make_image((0, 255, 0)))

    batch = batch_tensor_images([image_a, image_b])

    assert isinstance(batch, torch.Tensor)
    assert batch.shape == (2, 4, 4, 3)
