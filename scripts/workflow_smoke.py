from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib import parse, request
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import comfyui_smoke
from utils.image_io import bytes_to_pil_image


DEFAULT_TEXT_WORKFLOW_PATH = ROOT / "examples" / "minimal_text_workflow.json"
DEFAULT_IMAGE_WORKFLOW_PATH = ROOT / "examples" / "minimal_image_workflow.json"

TEXT_WIDGET_KEYS = [
    "prompt",
    "model",
    "resolution_preset",
    "width",
    "height",
    "n",
    "quality",
    "output_format",
    "background",
    "style",
    "moderation",
    "output_compression",
    "partial_images",
    "stream",
    "api_key",
]

LOAD_IMAGE_WIDGET_KEYS = [
    "image",
]

SAVE_IMAGE_WIDGET_KEYS = [
    "filename_prefix",
]


@dataclass
class WorkflowSmokeReport:
    ok: bool
    lines: list[str]

    def render(self) -> str:
        return "\n".join(self.lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit a minimal Nanaix workflow to ComfyUI /prompt for smoke testing.")
    parser.add_argument("--host", default="127.0.0.1", help="ComfyUI host")
    parser.add_argument("--port", type=int, default=8188, help="ComfyUI port")
    parser.add_argument("--workflow", default=str(DEFAULT_TEXT_WORKFLOW_PATH), help="Workflow JSON path")
    parser.add_argument("--comfy-root", default="", help="Optional ComfyUI root directory containing main.py for local launch")
    parser.add_argument("--python", default="", help="Optional ComfyUI Python executable for local launch")
    parser.add_argument("--timeout", type=float, default=30.0, help="Maximum seconds to wait when launching ComfyUI locally")
    parser.add_argument(
        "--verify-saved-images",
        action="store_true",
        help="Wait for workflow completion and verify that SaveImage produced output files.",
    )
    return parser.parse_args()


def safe_print_report(text: str) -> None:
    output = f"{text}\n"
    try:
        sys.stdout.write(output)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        sanitized = output.encode(encoding, errors="replace").decode(encoding, errors="replace")
        sys.stdout.write(sanitized)
    sys.stdout.flush()


def load_workflow(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def widget_inputs_for_node(node: dict) -> dict:
    node_type = node.get("type")
    if node_type in {"Nanaix_Text", "Nanaix_Image"}:
        keys = TEXT_WIDGET_KEYS
    elif node_type == "LoadImage":
        keys = LOAD_IMAGE_WIDGET_KEYS
    elif node_type == "SaveImage":
        keys = SAVE_IMAGE_WIDGET_KEYS
    else:
        return {}
    values = node.get("widgets_values", [])
    return {
        key: values[index]
        for index, key in enumerate(keys)
        if index < len(values)
    }


def build_prompt_payload(workflow_path: Path) -> dict:
    workflow = load_workflow(workflow_path)
    link_map = {link[0]: link for link in workflow.get("links", [])}
    prompt: dict[str, dict] = {}

    for node in workflow.get("nodes", []):
        node_id = str(node["id"])
        inputs: dict[str, object] = {}
        for input_spec in node.get("inputs", []) or []:
            link_id = input_spec.get("link")
            if link_id is None:
                continue
            link = link_map[link_id]
            inputs[input_spec["name"]] = [str(link[1]), link[2]]

        inputs.update(widget_inputs_for_node(node))
        prompt[node_id] = {
            "class_type": node["type"],
            "inputs": inputs,
        }

    return {"prompt": prompt}


def queue_prompt(host: str, port: int, payload: dict) -> dict:
    url = f"http://{host}:{port}/prompt"
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        try:
            body = error.read().decode("utf-8", errors="replace").strip()
        except Exception:
            body = ""
        parsed = parse_validation_error_response(body)
        if parsed is not None:
            return parsed
        details = f" Response body: {body}" if body else ""
        raise RuntimeError(f"ComfyUI /prompt returned HTTP {error.code} at {url}: {error.reason}.{details}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach ComfyUI /prompt at {url}: {error}") from error
    except TimeoutError as error:
        raise RuntimeError(f"Could not reach ComfyUI /prompt at {url}: timed out") from error

    if "prompt_id" not in data:
        raise RuntimeError(f"ComfyUI /prompt response did not include prompt_id: {data}")
    return data


def parse_validation_error_response(body: str) -> dict | None:
    if not body:
        return None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    node_errors = payload.get("node_errors")
    if not isinstance(node_errors, dict) or not node_errors:
        return None
    error_info = payload.get("error")
    if not isinstance(error_info, dict):
        return None
    if error_info.get("type") != "prompt_outputs_failed_validation":
        return None
    normalized = dict(payload)
    normalized.setdefault("prompt_id", "validation_failed")
    return normalized


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


def run_local_prompt_smoke(
    workflow_path: Path,
    comfy_root: Path,
    python_executable: Path,
    host: str,
    port: int,
    timeout: float,
    verify_saved_images: bool = False,
) -> WorkflowSmokeReport:
    payload = build_prompt_payload(workflow_path)
    prepared_input_paths = prepare_local_workflow_inputs(workflow_path, payload, comfy_root)
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
    lines = [f"Launching local ComfyUI for workflow smoke on {host}:{port}"]
    if prepared_input_paths:
        lines.extend(f"Prepared workflow input: {path}" for path in prepared_input_paths)

    try:
        while time.time() - started_at <= timeout:
            if process.poll() not in (None,):
                exit_lines = [f"ComfyUI exited early with code {process.poll()}"]
                exit_lines.extend(comfyui_smoke.collect_process_output(process))
                return WorkflowSmokeReport(False, lines + exit_lines)

            if not comfyui_smoke.probe_server_ready(host, port):
                time.sleep(1.0)
                continue
            try:
                result = queue_prompt(host, port, payload)
                lines.append(f"Queued workflow prompt_id: {result['prompt_id']}")
                node_errors = result.get("node_errors", {})
                lines.append(f"Node errors: {json.dumps(node_errors, ensure_ascii=True)}")
                if verify_saved_images and not node_errors:
                    prompt_id = str(result["prompt_id"])
                    history_payload = wait_for_history(host, port, prompt_id, timeout)
                    images = extract_saved_images_from_history(history_payload)
                    if not images:
                        return WorkflowSmokeReport(False, lines + [f"Prompt {prompt_id} completed without saved output images"])
                    lines.append(f"Saved images: {len(images)}")
                    first = images[0]
                    filename = str(first.get("filename", "<unknown>"))
                    subfolder = str(first.get("subfolder", "") or "")
                    image_type = str(first.get("type", "output") or "output")
                    location = image_type if not subfolder else f"{image_type}/{subfolder}"
                    lines.append(f"First saved image: {filename}")
                    lines.append(f"Saved image location: {location}")
                return WorkflowSmokeReport(True, lines)
            except RuntimeError as error:
                if "Could not reach ComfyUI /prompt" not in str(error):
                    return WorkflowSmokeReport(False, lines + [str(error)])
                time.sleep(1.0)

        comfyui_smoke.stop_process(process)
        timeout_lines = [f"Timed out after {timeout:.1f}s waiting to submit workflow"]
        timeout_lines.extend(comfyui_smoke.collect_process_output(process))
        return WorkflowSmokeReport(False, lines + timeout_lines)
    finally:
        if process.poll() is None:
            comfyui_smoke.stop_process(process)


def submit_multiple_workflow_smokes(
    workflow_paths: list[Path],
    comfy_root: Path,
    python_executable: Path,
    host: str,
    port: int,
    timeout: float,
    verify_saved_images: bool = False,
) -> list[WorkflowSmokeReport]:
    payloads = [(workflow_path, build_prompt_payload(workflow_path)) for workflow_path in workflow_paths]
    prepared_input_paths_by_workflow: dict[Path, list[Path]] = {}
    for workflow_path, payload in payloads:
        prepared_input_paths_by_workflow[workflow_path] = prepare_local_workflow_inputs(workflow_path, payload, comfy_root)

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
    launch_lines = [f"Launching local ComfyUI for workflow smoke on {host}:{port}"]

    try:
        while time.time() - started_at <= timeout:
            if process.poll() not in (None,):
                exit_lines = [f"ComfyUI exited early with code {process.poll()}"]
                exit_lines.extend(comfyui_smoke.collect_process_output(process))
                return [WorkflowSmokeReport(False, launch_lines + exit_lines) for _ in workflow_paths]

            if not comfyui_smoke.probe_server_ready(host, port):
                time.sleep(1.0)
                continue

            try:
                reports: list[WorkflowSmokeReport] = []
                for index, (workflow_path, payload) in enumerate(payloads):
                    result = queue_prompt(host, port, payload)
                    lines: list[str] = []
                    if index == 0:
                        lines.extend(launch_lines)
                    lines.extend(
                        f"Prepared workflow input: {path}"
                        for path in prepared_input_paths_by_workflow.get(workflow_path, [])
                    )
                    lines.append(f"Workflow: {workflow_path.name}")
                    lines.append(f"Queued workflow prompt_id: {result['prompt_id']}")
                    node_errors = result.get("node_errors", {})
                    lines.append(f"Node errors: {json.dumps(node_errors, ensure_ascii=True)}")
                    if verify_saved_images and not node_errors:
                        prompt_id = str(result["prompt_id"])
                        history_payload = wait_for_history(host, port, prompt_id, timeout)
                        images = extract_saved_images_from_history(history_payload)
                        if not images:
                            return [
                                WorkflowSmokeReport(False, launch_lines + [f"Prompt {prompt_id} completed without saved output images"])
                                for _ in workflow_paths
                            ]
                        lines.append(f"Saved images: {len(images)}")
                        first = images[0]
                        filename = str(first.get("filename", "<unknown>"))
                        subfolder = str(first.get("subfolder", "") or "")
                        image_type = str(first.get("type", "output") or "output")
                        location = image_type if not subfolder else f"{image_type}/{subfolder}"
                        lines.append(f"First saved image: {filename}")
                        lines.append(f"Saved image location: {location}")
                    reports.append(WorkflowSmokeReport(True, lines))
                return reports
            except RuntimeError as error:
                if "Could not reach ComfyUI /prompt" not in str(error):
                    return [WorkflowSmokeReport(False, launch_lines + [str(error)]) for _ in workflow_paths]
                time.sleep(1.0)

        timeout_lines = [f"Timed out after {timeout:.1f}s waiting to submit workflow"]
        timeout_lines.extend(comfyui_smoke.collect_process_output(process))
        return [WorkflowSmokeReport(False, launch_lines + timeout_lines) for _ in workflow_paths]
    finally:
        if process.poll() is None:
            comfyui_smoke.stop_process(process)


def prepare_local_workflow_inputs(workflow_path: Path, payload: dict, comfy_root: Path) -> list[Path]:
    workflow_name = workflow_path.name.lower()
    if "image" not in workflow_name:
        return []

    prompt = payload.get("prompt", {})
    if not isinstance(prompt, dict):
        return []

    input_dir = comfy_root / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    prepared_paths: list[Path] = []

    for node in prompt.values():
        if not isinstance(node, dict) or node.get("class_type") != "LoadImage":
            continue
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        image_name = inputs.get("image")
        if not isinstance(image_name, str) or not image_name.strip():
            continue
        target_path = input_dir / image_name
        if target_path.exists():
            prepared_paths.append(target_path)
            continue

        source_path = workflow_path.parent / image_name
        if source_path.exists():
            shutil.copyfile(source_path, target_path)
            prepared_paths.append(target_path)
            continue

        image = bytes_to_pil_image(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
            b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        image.save(target_path)
        prepared_paths.append(target_path)

    return prepared_paths


def submit_workflow_smoke(
    host: str,
    port: int,
    workflow_path: Path = DEFAULT_TEXT_WORKFLOW_PATH,
    comfy_root: Path | None = None,
    python_executable: Path | None = None,
    timeout: float = 30.0,
    verify_saved_images: bool = False,
) -> WorkflowSmokeReport:
    if comfy_root is not None and python_executable is not None:
        return run_local_prompt_smoke(
            workflow_path,
            comfy_root,
            python_executable,
            host,
            port,
            timeout,
            verify_saved_images=verify_saved_images,
        )

    payload = build_prompt_payload(workflow_path)
    result = queue_prompt(host, port, payload)
    lines = [f"Queued workflow prompt_id: {result['prompt_id']}"]
    node_errors = result.get("node_errors", {})
    lines.append(f"Node errors: {json.dumps(node_errors, ensure_ascii=True)}")
    if verify_saved_images and not node_errors:
        prompt_id = str(result["prompt_id"])
        try:
            history_payload = wait_for_history(host, port, prompt_id, timeout)
            images = extract_saved_images_from_history(history_payload)
        except RuntimeError as error:
            return WorkflowSmokeReport(False, lines + [str(error)])
        if not images:
            return WorkflowSmokeReport(False, lines + [f"Prompt {prompt_id} completed without saved output images"])
        lines.append(f"Saved images: {len(images)}")
        first = images[0]
        filename = str(first.get("filename", "<unknown>"))
        subfolder = str(first.get("subfolder", "") or "")
        image_type = str(first.get("type", "output") or "output")
        location = image_type if not subfolder else f"{image_type}/{subfolder}"
        lines.append(f"First saved image: {filename}")
        lines.append(f"Saved image location: {location}")
    return WorkflowSmokeReport(True, lines)


def submit_text_workflow_smoke(
    host: str,
    port: int,
    workflow_path: Path = DEFAULT_TEXT_WORKFLOW_PATH,
    comfy_root: Path | None = None,
    python_executable: Path | None = None,
    timeout: float = 30.0,
    verify_saved_images: bool = False,
) -> WorkflowSmokeReport:
    return submit_workflow_smoke(
        host=host,
        port=port,
        workflow_path=workflow_path,
        comfy_root=comfy_root,
        python_executable=python_executable,
        timeout=timeout,
        verify_saved_images=verify_saved_images,
    )


def main() -> int:
    args = parse_args()
    comfy_root_arg = getattr(args, "comfy_root", "")
    python_arg = getattr(args, "python", "")
    timeout = float(getattr(args, "timeout", 30.0))
    verify_saved_images = bool(getattr(args, "verify_saved_images", False))
    comfy_root = Path(comfy_root_arg).resolve() if comfy_root_arg else None
    python_executable = Path(python_arg).resolve() if python_arg else None

    if (comfy_root is None) != (python_executable is None):
        print("Both --comfy-root and --python are required together for local launch.")
        return 1

    try:
        submit_kwargs = {
            "host": args.host,
            "port": args.port,
            "workflow_path": Path(args.workflow).resolve(),
            "verify_saved_images": verify_saved_images,
        }
        if comfy_root is not None and python_executable is not None:
            submit_kwargs["comfy_root"] = comfy_root
            submit_kwargs["python_executable"] = python_executable
            submit_kwargs["timeout"] = timeout
        report = submit_workflow_smoke(**submit_kwargs)
    except RuntimeError as error:
        print(str(error))
        return 1

    safe_print_report(report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
