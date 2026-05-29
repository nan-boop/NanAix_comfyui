from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from urllib import parse, request
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import comfyui_smoke, workflow_smoke
from utils.errors import warn_ignored_image2_only_options

IMAGE2_KEY_ENV = "NANAIX_IMAGE2_API_KEY"
BANANA_KEY_ENV = "NANAIX_BANANA_API_KEY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a live Nanaix ComfyUI generation smoke that saves an output image.")
    parser.add_argument("--comfy-root", default="", help="Optional ComfyUI root directory containing main.py for local launch.")
    parser.add_argument("--python", default="", help="Optional ComfyUI Python executable for local launch.")
    parser.add_argument("--mode", default="text", choices=["text", "image"], help="Which Nanaix node path to test.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8188)
    parser.add_argument("--model", default="gpt-image-2")
    parser.add_argument("--prompt", default="A red lantern on a rainy street")
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
    parser.add_argument("--filename-prefix", default="nanaix_live_test")
    parser.add_argument("--image2-key", default="")
    parser.add_argument("--banana-key", default="")
    parser.add_argument("--input-image-name", default="workflow_smoke_input.png", help="Input image filename for image mode.")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--fail-if-missing-key", action="store_true")
    args = parser.parse_args()
    args.model_was_explicit = "--model" in sys.argv[1:]
    return args


def resolve_live_keys(image2_key: str, banana_key: str) -> tuple[str, str]:
    return image2_key or os.environ.get(IMAGE2_KEY_ENV, ""), banana_key or os.environ.get(BANANA_KEY_ENV, "")


def choose_live_model_for_keys(
    image2_key: str,
    banana_key: str,
    preferred_model: str = "gpt-image-2",
    image2_models_fn=lambda key: __import__("services.image2_client", fromlist=["Image2Client"]).Image2Client(key).list_models(node_name="LiveSmoke"),
    banana_models_fn=lambda key: __import__("services.banana_client", fromlist=["BananaClient"]).BananaClient(key).list_models(node_name="LiveSmoke"),
) -> tuple[str, list[str]]:
    lines: list[str] = []

    if preferred_model == "gpt-image-2" and image2_key:
        try:
            image2_models = image2_models_fn(image2_key)
        except Exception as error:
            lines.append(f"live model selection: image-2 visibility check failed: {error}")
        else:
            if "gpt-image-2" in image2_models:
                lines.append("live model selection: selected model gpt-image-2 via image-2 visibility")
                return "gpt-image-2", lines
            visible = ", ".join(image2_models) if image2_models else "none"
            lines.append(f"live model selection: gpt-image-2 is not visible for the current image-2 key (visible: {visible})")

    if banana_key:
        try:
            banana_models = banana_models_fn(banana_key)
        except Exception as error:
            lines.append(f"live model selection: nano-banana visibility check failed: {error}")
        else:
            for candidate in ("nano-banana-pro", "nano-banana-2"):
                if candidate in banana_models:
                    lines.append(f"live model selection: selected model {candidate} via nano-banana visibility")
                    return candidate, lines
            visible = ", ".join(banana_models) if banana_models else "none"
            lines.append(f"live model selection: no supported nano-banana live model is visible (visible: {visible})")

    lines.append(f"live model selection: falling back to {preferred_model}")
    return preferred_model, lines


def build_text_prompt(
    *,
    prompt_text: str,
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
    filename_prefix: str,
) -> dict[str, dict]:
    return {
        "1": {
            "class_type": "Nanaix_Text",
            "inputs": {
                "prompt": prompt_text,
                "model": model,
                "width": width,
                "height": height,
                "n": n,
                "quality": quality,
                "output_format": output_format,
                "background": background,
                "style": style,
                "moderation": moderation,
                "output_compression": output_compression,
                "partial_images": partial_images,
                "stream": stream,
                "api_key": api_key,
            },
        },
        "2": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["1", 0],
                "filename_prefix": filename_prefix,
            },
        },
    }


def build_image_prompt(
    *,
    prompt_text: str,
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
    filename_prefix: str,
    input_image_name: str,
) -> dict[str, dict]:
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {
                "image": input_image_name,
            },
        },
        "2": {
            "class_type": "Nanaix_Image",
            "inputs": {
                "image_1": ["1", 0],
                "prompt": prompt_text,
                "model": model,
                "width": width,
                "height": height,
                "n": n,
                "quality": quality,
                "output_format": output_format,
                "background": background,
                "style": style,
                "moderation": moderation,
                "output_compression": output_compression,
                "partial_images": partial_images,
                "stream": stream,
                "api_key": api_key,
            },
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["2", 0],
                "filename_prefix": filename_prefix,
            },
        },
    }


def queue_prompt(host: str, port: int, prompt: dict[str, dict]) -> dict:
    payload = {
        "prompt": prompt,
        "prompt_id": str(uuid.uuid4()),
        "client_id": str(uuid.uuid4()),
    }
    req = request.Request(
        f"http://{host}:{port}/prompt",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ComfyUI /prompt failed with HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach ComfyUI /prompt: {error.reason}") from error


def wait_for_history(host: str, port: int, prompt_id: str, timeout: float) -> dict:
    deadline = time.time() + timeout
    url = f"http://{host}:{port}/history/{parse.quote(prompt_id)}"
    while time.time() < deadline:
        req = request.Request(url, method="GET")
        with request.urlopen(req, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if isinstance(payload, dict) and prompt_id in payload:
            return payload[prompt_id]
        time.sleep(1.0)
    raise RuntimeError(f"Timed out waiting for ComfyUI history for prompt {prompt_id}")


def extract_saved_images_from_history(history_payload: dict) -> list[dict]:
    outputs = history_payload.get("outputs", {})
    images: list[dict] = []
    if not isinstance(outputs, dict):
        return images
    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue
        node_images = node_output.get("images", [])
        if isinstance(node_images, list):
            for image in node_images:
                if isinstance(image, dict) and "filename" in image:
                    images.append(image)
    return images


def summarize_saved_images(*, mode: str, prompt_id: str, images: list[dict]) -> str:
    parts = [f"mode={mode}", f"prompt_id={prompt_id}", f"saved={len(images)}"]
    if images:
        first = images[0]
        filename = first.get("filename", "<unknown>")
        subfolder = str(first.get("subfolder", "") or "")
        image_type = str(first.get("type", "output") or "output")
        location = image_type if not subfolder else f"{image_type}/{subfolder}"
        parts.append(f"first_file={filename}")
        parts.append(f"location={location}")
    return " ".join(parts)


def ensure_local_input_image(*, comfy_root: Path, input_image_name: str) -> Path:
    payload = {
        "prompt": {
            "1": {
                "class_type": "LoadImage",
                "inputs": {
                    "image": input_image_name,
                },
            }
        }
    }
    prepared = workflow_smoke.prepare_local_workflow_inputs(
        workflow_path=ROOT / "examples" / "minimal_image_workflow.json",
        payload=payload,
        comfy_root=comfy_root,
    )
    if not prepared:
        raise RuntimeError(f"Failed to prepare local input image {input_image_name}")
    return prepared[0]


def run_live_text_smoke(
    *,
    host: str,
    port: int,
    model: str,
    prompt_text: str,
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
    filename_prefix: str,
    image2_key: str,
    banana_key: str,
    timeout: float,
) -> dict:
    if model != "gpt-image-2":
        warn_ignored_image2_only_options(
            model=model,
            background=background,
            style=style,
            moderation=moderation,
            output_compression=output_compression,
            partial_images=partial_images,
            stream=stream,
        )
    prompt = build_text_prompt(
        prompt_text=prompt_text,
        model=model,
        width=width,
        height=height,
        n=n,
        quality=quality,
        output_format=output_format,
        background=background,
        style=style,
        moderation=moderation,
        output_compression=output_compression,
        partial_images=partial_images,
        stream=stream,
        api_key=image2_key if model.startswith("gpt-image-") else banana_key,
        filename_prefix=filename_prefix,
    )
    response = queue_prompt(host, port, prompt)
    prompt_id = response.get("prompt_id")
    if not isinstance(prompt_id, str) or not prompt_id:
        raise RuntimeError(f"ComfyUI /prompt did not return a prompt_id: {response}")

    history_payload = wait_for_history(host, port, prompt_id, timeout)
    images = extract_saved_images_from_history(history_payload)
    if not images:
        raise RuntimeError(f"Prompt {prompt_id} completed without saved output images")
    return {"prompt_id": prompt_id, "images": images, "history": history_payload}


def run_live_image_smoke(
    *,
    host: str,
    port: int,
    model: str,
    prompt_text: str,
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
    filename_prefix: str,
    image2_key: str,
    banana_key: str,
    timeout: float,
    input_image_name: str,
) -> dict:
    if model != "gpt-image-2":
        warn_ignored_image2_only_options(
            model=model,
            background=background,
            style=style,
            moderation=moderation,
            output_compression=output_compression,
            partial_images=partial_images,
            stream=stream,
        )
    prompt = build_image_prompt(
        prompt_text=prompt_text,
        model=model,
        width=width,
        height=height,
        n=n,
        quality=quality,
        output_format=output_format,
        background=background,
        style=style,
        moderation=moderation,
        output_compression=output_compression,
        partial_images=partial_images,
        stream=stream,
        api_key=image2_key if model.startswith("gpt-image-") else banana_key,
        filename_prefix=filename_prefix,
        input_image_name=input_image_name,
    )
    response = queue_prompt(host, port, prompt)
    prompt_id = response.get("prompt_id")
    if not isinstance(prompt_id, str) or not prompt_id:
        raise RuntimeError(f"ComfyUI /prompt did not return a prompt_id: {response}")

    history_payload = wait_for_history(host, port, prompt_id, timeout)
    images = extract_saved_images_from_history(history_payload)
    if not images:
        raise RuntimeError(f"Prompt {prompt_id} completed without saved output images")
    return {"prompt_id": prompt_id, "images": images, "history": history_payload}


def run_local_live_text_smoke(
    *,
    comfy_root: Path,
    python_executable: Path,
    host: str,
    port: int,
    model: str,
    prompt_text: str,
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
    filename_prefix: str,
    image2_key: str,
    banana_key: str,
    timeout: float,
) -> dict:
    process = comfyui_smoke.launch_comfyui_process(
        [
            str(python_executable),
            str(comfy_root / "main.py"),
            "--listen",
            host,
            "--port",
            str(port),
            "--disable-auto-launch",
            "--dont-print-server",
            "--disable-all-custom-nodes",
            "--whitelist-custom-nodes",
            "nanaix_Comfy",
        ],
        comfy_root,
    )
    started_at = time.time()
    try:
        while time.time() - started_at <= timeout:
            if process.poll() not in (None,):
                exit_lines = comfyui_smoke.collect_process_output(process)
                raise RuntimeError(
                    "Local ComfyUI exited before live smoke could run."
                    + (f" Logs: {' | '.join(exit_lines)}" if exit_lines else "")
                )
            if not comfyui_smoke.probe_server_ready(host, port):
                time.sleep(1.0)
                continue
            return run_live_text_smoke(
                host=host,
                port=port,
                model=model,
                prompt_text=prompt_text,
                width=width,
                height=height,
                n=n,
                quality=quality,
                output_format=output_format,
                background=background,
                style=style,
                moderation=moderation,
                output_compression=output_compression,
                partial_images=partial_images,
                stream=stream,
                filename_prefix=filename_prefix,
                image2_key=image2_key,
                banana_key=banana_key,
                timeout=timeout,
            )
        raise RuntimeError(f"Timed out after {timeout:.1f}s waiting for local ComfyUI before live smoke")
    finally:
        if process.poll() is None:
            comfyui_smoke.stop_process(process)


def run_local_live_image_smoke(
    *,
    comfy_root: Path,
    python_executable: Path,
    host: str,
    port: int,
    model: str,
    prompt_text: str,
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
    filename_prefix: str,
    image2_key: str,
    banana_key: str,
    timeout: float,
    input_image_name: str,
) -> dict:
    ensure_local_input_image(comfy_root=comfy_root, input_image_name=input_image_name)
    process = comfyui_smoke.launch_comfyui_process(
        [
            str(python_executable),
            str(comfy_root / "main.py"),
            "--listen",
            host,
            "--port",
            str(port),
            "--disable-auto-launch",
            "--dont-print-server",
            "--disable-all-custom-nodes",
            "--whitelist-custom-nodes",
            "nanaix_Comfy",
        ],
        comfy_root,
    )
    started_at = time.time()
    try:
        while time.time() - started_at <= timeout:
            if process.poll() not in (None,):
                exit_lines = comfyui_smoke.collect_process_output(process)
                raise RuntimeError(
                    "Local ComfyUI exited before live image smoke could run."
                    + (f" Logs: {' | '.join(exit_lines)}" if exit_lines else "")
                )
            if not comfyui_smoke.probe_server_ready(host, port):
                time.sleep(1.0)
                continue
            return run_live_image_smoke(
                host=host,
                port=port,
                model=model,
                prompt_text=prompt_text,
                width=width,
                height=height,
                n=n,
                quality=quality,
                output_format=output_format,
                background=background,
                style=style,
                moderation=moderation,
                output_compression=output_compression,
                partial_images=partial_images,
                stream=stream,
                filename_prefix=filename_prefix,
                image2_key=image2_key,
                banana_key=banana_key,
                timeout=timeout,
                input_image_name=input_image_name,
            )
        raise RuntimeError(f"Timed out after {timeout:.1f}s waiting for local ComfyUI before live image smoke")
    finally:
        if process.poll() is None:
            comfyui_smoke.stop_process(process)


def main() -> int:
    try:
        args = parse_args()
        mode = getattr(args, "mode", "text")
        image2_key, banana_key = resolve_live_keys(args.image2_key, args.banana_key)
        selected_model = args.model
        if not getattr(args, "model_was_explicit", False):
            selected_model, selection_lines = choose_live_model_for_keys(image2_key, banana_key, preferred_model=args.model)
            for line in selection_lines:
                print(line)

        required_key = image2_key if selected_model.startswith("gpt-image-") else banana_key
        if not required_key:
            required_env = IMAGE2_KEY_ENV if selected_model.startswith("gpt-image-") else BANANA_KEY_ENV
            message = (
                f"Skipping live ComfyUI smoke because {selected_model} requires a configured API key. "
                f"Set --{'image2-key' if selected_model.startswith('gpt-image-') else 'banana-key'} or {required_env}."
            )
            if args.fail_if_missing_key:
                print(message)
                return 1
            print(message)
            return 0

        comfy_root_arg = getattr(args, "comfy_root", "")
        python_arg = getattr(args, "python", "")
        if bool(comfy_root_arg) != bool(python_arg):
            print("Both --comfy-root and --python are required together for local launch.")
            return 1

        run_kwargs = {
            "host": args.host,
            "port": args.port,
            "model": selected_model,
            "prompt_text": args.prompt,
            "width": args.width,
            "height": args.height,
            "n": args.n,
            "quality": args.quality,
            "output_format": args.output_format,
            "background": getattr(args, "background", "auto"),
            "style": getattr(args, "style", "natural"),
            "moderation": getattr(args, "moderation", "auto"),
            "output_compression": getattr(args, "output_compression", 0),
            "partial_images": getattr(args, "partial_images", 0),
            "stream": getattr(args, "stream", False),
            "filename_prefix": args.filename_prefix,
            "image2_key": image2_key,
            "banana_key": banana_key,
            "timeout": args.timeout,
        }
        if comfy_root_arg and python_arg:
            if mode == "image":
                result = run_local_live_image_smoke(
                    comfy_root=Path(comfy_root_arg).resolve(),
                    python_executable=Path(python_arg).resolve(),
                    input_image_name=getattr(args, "input_image_name", "workflow_smoke_input.png"),
                    **run_kwargs,
                )
            else:
                result = run_local_live_text_smoke(
                    comfy_root=Path(comfy_root_arg).resolve(),
                    python_executable=Path(python_arg).resolve(),
                    **run_kwargs,
                )
        else:
            if mode == "image":
                result = run_live_image_smoke(
                    input_image_name=getattr(args, "input_image_name", "workflow_smoke_input.png"),
                    **run_kwargs,
                )
            else:
                result = run_live_text_smoke(**run_kwargs)
        print(
            "Live ComfyUI smoke "
            + summarize_saved_images(
                mode=mode,
                prompt_id=result["prompt_id"],
                images=result["images"],
            )
        )
        return 0
    except Exception as error:
        print(str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
