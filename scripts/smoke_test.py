from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.banana_client import BananaClient
from services.image2_client import Image2Client
from utils.errors import warn_ignored_image2_only_options
from utils.image_io import pil_image_to_tensor, tensor_image_to_pil
from utils.size_mapping import map_banana_size, map_image2_size


IMAGE2_KEY_ENV = "NANAIX_IMAGE2_API_KEY"
BANANA_KEY_ENV = "NANAIX_BANANA_API_KEY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Nanaix API smoke test outside ComfyUI.")
    parser.add_argument("--model", required=True, choices=["gpt-image-2", "nano-banana-2", "nano-banana-pro"])
    parser.add_argument("--prompt", default="")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--quality", default="high", choices=["high", "medium", "low"])
    parser.add_argument("--output-format", default="png", choices=["png", "webp", "jpeg"])
    parser.add_argument("--background", default="auto", choices=["auto", "transparent"])
    parser.add_argument("--style", default="natural", choices=["natural", "vivid"])
    parser.add_argument("--moderation", default="auto", choices=["auto", "low"])
    parser.add_argument("--output-compression", type=int, default=0)
    parser.add_argument("--partial-images", type=int, default=0)
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--output", default="", help="Output image path")
    parser.add_argument("--image2-key", default="")
    parser.add_argument("--banana-key", default="")
    parser.add_argument("--list-models", action="store_true", help="List models for the selected provider and exit")
    parser.add_argument("--preflight", action="store_true", help="Run a provider/key visibility preflight check and exit")
    parser.add_argument("--reference-image", action="append", default=[], help="Optional reference image path. Repeat up to 8 times.")
    return parser.parse_args()


def load_reference_tensors(paths: list[str]) -> list:
    tensors = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        tensors.append(pil_image_to_tensor(image))
    return tensors


def output_paths(base_path: Path, count: int) -> list[Path]:
    if count <= 1:
        return [base_path]

    suffix = base_path.suffix
    stem = base_path.stem
    return [
        base_path.with_name(f"{stem}_{index}{suffix}")
        for index in range(1, count + 1)
    ]


def resolve_key(cli_value: str, env_name: str) -> str:
    return cli_value or os.environ.get(env_name, "")


def run_preflight(model: str, client: object) -> int:
    try:
        models = client.list_models(node_name="SmokeTest")
    except Exception as error:
        if model == "gpt-image-2":
            print(f"image-2: FAIL - {error}")
        else:
            print(f"nano-banana: FAIL - {error}")
        return 0

    if model == "gpt-image-2":
        if "gpt-image-2" in models:
            print(f"image-2: OK - visible models: {', '.join(models)}")
        else:
            visible = ", ".join(models) if models else "none"
            print(f"image-2: FAIL - gpt-image-2 is not visible for this key (visible: {visible})")
        return 0

    missing_models = [expected for expected in ("nano-banana-2", "nano-banana-pro") if expected not in models]
    if missing_models:
        visible = ", ".join(models) if models else "none"
        print(f"nano-banana: FAIL - missing expected models: {', '.join(missing_models)} (visible: {visible})")
    else:
        print(f"nano-banana: OK - visible models: {', '.join(models)}")
    return 0


def main() -> int:
    args = parse_args()
    image2_key = resolve_key(args.image2_key, IMAGE2_KEY_ENV)
    banana_key = resolve_key(args.banana_key, BANANA_KEY_ENV)

    if args.model == "gpt-image-2":
        if not image2_key:
            raise ValueError(f"--image2-key is required for gpt-image-2 (or set {IMAGE2_KEY_ENV})")
        client = Image2Client(image2_key)
        if args.list_models:
            for model in client.list_models(node_name="SmokeTest"):
                print(model)
            return 0
        if args.preflight:
            return run_preflight(args.model, client)
    else:
        if not banana_key:
            raise ValueError(f"--banana-key is required for nano-banana models (or set {BANANA_KEY_ENV})")
        client = BananaClient(banana_key)
        if args.list_models:
            for model in client.list_models(node_name="SmokeTest"):
                print(model)
            return 0
        if args.preflight:
            return run_preflight(args.model, client)

    if not args.prompt:
        raise ValueError("--prompt is required unless --list-models or --preflight is used")
    if not args.output:
        raise ValueError("--output is required unless --list-models or --preflight is used")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    reference_images = load_reference_tensors(args.reference_image)

    if args.model == "gpt-image-2":
        if reference_images:
            images = client.edit(
                node_name="SmokeTest",
                prompt=args.prompt,
                model=args.model,
                size=map_image2_size(args.width, args.height),
                n=args.n,
                quality=args.quality,
                output_format=args.output_format,
                background=args.background,
                style=args.style,
                moderation=args.moderation,
                output_compression=args.output_compression,
                partial_images=args.partial_images,
                stream=args.stream,
                reference_images=reference_images,
            )
        else:
            images = client.generate(
                node_name="SmokeTest",
                prompt=args.prompt,
                model=args.model,
                size=map_image2_size(args.width, args.height),
                n=args.n,
                quality=args.quality,
                output_format=args.output_format,
                background=args.background,
                style=args.style,
                moderation=args.moderation,
                output_compression=args.output_compression,
                partial_images=args.partial_images,
                stream=args.stream,
            )
    else:
        aspect_ratio, image_size = map_banana_size(args.width, args.height)
        warn_ignored_image2_only_options(
            model=args.model,
            background=args.background,
            style=args.style,
            moderation=args.moderation,
            output_compression=args.output_compression,
            partial_images=args.partial_images,
            stream=args.stream,
        )
        images = client.generate(
            node_name="SmokeTest",
            prompt=args.prompt,
            model=args.model,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            n=args.n,
            quality=args.quality,
            output_format=args.output_format,
            reference_images=reference_images or None,
        )

    saved_paths = output_paths(output_path, len(images))
    for image_tensor, path in zip(images, saved_paths):
        tensor_image_to_pil(image_tensor).save(path)
    print(f"Saved {len(saved_paths)} smoke test image(s) to {output_path.parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
