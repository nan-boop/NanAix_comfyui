from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import comfyui_smoke, deploy_to_comfyui, doctor, find_comfyui, live_comfy_smoke, verify_install, workflow_smoke


@dataclass
class RunbookReport:
    ok: bool
    lines: list[str]
    custom_nodes_path: Path | None = None
    python_executable: Path | None = None

    def render(self) -> str:
        return "\n".join(self.lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Nanaix ComfyUI install and verification steps end-to-end.")
    parser.add_argument(
        "--custom-nodes",
        default="",
        help="Optional custom_nodes path. If omitted, the best candidate will be auto-detected.",
    )
    parser.add_argument(
        "--python",
        default="",
        help="Optional ComfyUI Python executable. If omitted, the best embedded python.exe will be auto-detected.",
    )
    parser.add_argument(
        "--roots",
        nargs="*",
        default=[str(root) for root in find_comfyui.DEFAULT_ROOTS],
        help="Optional roots to scan when auto-detecting ComfyUI paths.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing plugin installation.")
    parser.add_argument("--smoke-host", default="127.0.0.1", help="Host to bind the registration smoke check ComfyUI server to.")
    parser.add_argument("--smoke-port", type=int, default=8191, help="Port to bind the registration smoke check ComfyUI server to.")
    parser.add_argument("--smoke-timeout", type=float, default=45.0, help="Maximum seconds to wait for registration smoke check node discovery.")
    parser.add_argument("--skip-smoke", action="store_true", help="Skip the final registration smoke check.")
    return parser.parse_args()


def find_best_comfy_python(roots: list[Path], limit: int = 20) -> Path | None:
    return find_comfyui.find_best_comfy_python_candidate(roots, limit=limit)


def choose_default_live_model(
    image2_key: str,
    banana_key: str,
    image2_models_fn: Callable[[str], list[str]] = lambda key: live_comfy_smoke.Image2Client(key).list_models(node_name="Runbook"),
    banana_models_fn: Callable[[str], list[str]] = lambda key: live_comfy_smoke.BananaClient(key).list_models(node_name="Runbook"),
) -> tuple[str, list[str]]:
    lines: list[str] = []

    if image2_key:
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

    lines.append("live model selection: falling back to gpt-image-2")
    return "gpt-image-2", lines


def run_default_live_smoke(comfy_root: Path, python_executable: Path, host: str, port: int) -> RunbookReport:
    image2_key, banana_key = live_comfy_smoke.resolve_live_keys("", "")
    selected_model, selection_lines = choose_default_live_model(image2_key, banana_key)
    text_result = live_comfy_smoke.run_local_live_text_smoke(
        comfy_root=comfy_root,
        python_executable=python_executable,
        host=host,
        port=port,
        model=selected_model,
        prompt_text="A red lantern on a rainy street",
        width=1024,
        height=1024,
        n=1,
        quality="high",
        output_format="png",
        filename_prefix="nanaix_live_test",
        image2_key=image2_key,
        banana_key=banana_key,
        timeout=120.0,
    )
    image_result = live_comfy_smoke.run_local_live_image_smoke(
        comfy_root=comfy_root,
        python_executable=python_executable,
        host=host,
        port=port,
        model=selected_model,
        prompt_text="Turn this into a watercolor illustration",
        width=1024,
        height=1024,
        n=1,
        quality="high",
        output_format="png",
        filename_prefix="nanaix_live_edit_test",
        image2_key=image2_key,
        banana_key=banana_key,
        timeout=120.0,
        input_image_name="workflow_smoke_input.png",
    )
    return RunbookReport(
        True,
        [
            *selection_lines,
            live_comfy_smoke.summarize_saved_images(
                mode="text",
                prompt_id=str(text_result.get("prompt_id", "<unknown>")),
                images=text_result.get("images", []),
            ),
            live_comfy_smoke.summarize_saved_images(
                mode="image",
                prompt_id=str(image_result.get("prompt_id", "<unknown>")),
                images=image_result.get("images", []),
            ),
        ],
    )


def execute(
    *,
    custom_nodes: str,
    comfy_python: str,
    roots: list[Path],
    force: bool,
    smoke_host: str = "127.0.0.1",
    smoke_port: int = 8191,
    smoke_timeout: float = 45.0,
    run_smoke: bool = True,
    resolve_custom_nodes_path: Callable[[str, list[Path] | None], Path] = deploy_to_comfyui.resolve_custom_nodes_path,
    find_best_python: Callable[[list[Path]], Path | None] = find_best_comfy_python,
    deploy_fn: Callable[[Path, bool], tuple[bool, str]] = deploy_to_comfyui.deploy,
    verify_fn: Callable[[Path], tuple[bool, str]] = verify_install.verify_install,
    verify_runtime_fn: Callable[[Path, Path], tuple[bool, str]] = verify_install.verify_install_runtime,
    smoke_check_fn: Callable[[Path, Path, str, int, float], comfyui_smoke.SmokeReport] = comfyui_smoke.run_smoke_check,
    multi_workflow_smoke_fn: Callable[
        [list[Path], Path, Path, str, int, float, bool],
        list[workflow_smoke.WorkflowSmokeReport],
    ] = workflow_smoke.submit_multiple_workflow_smokes,
    doctor_self_check_fn: Callable[[], list[str]] = lambda: doctor.collect_provider_model_visibility(
        image2_api_key=live_comfy_smoke.resolve_live_keys("", "")[0],
        banana_api_key=live_comfy_smoke.resolve_live_keys("", "")[1],
    ),
    detect_live_keys_fn: Callable[[], bool] = lambda: any(live_comfy_smoke.resolve_live_keys("", "")),
    live_smoke_fn: Callable[[Path, Path, str, int], object] = run_default_live_smoke,
) -> RunbookReport:
    lines: list[str] = []
    custom_nodes_path = resolve_custom_nodes_path(custom_nodes, roots=roots)
    if custom_nodes.strip():
        lines.append(f"Using custom_nodes: {custom_nodes_path}")
    else:
        lines.append(f"Auto-detected custom_nodes: {custom_nodes_path}")

    try:
        for line in doctor_self_check_fn():
            lines.append(f"Doctor self-check: {line}")
    except Exception as error:
        lines.append(f"Doctor self-check: unavailable: {error}")

    python_executable: Path | None = None
    if comfy_python.strip():
        python_executable = Path(comfy_python).resolve()
        lines.append(f"Using ComfyUI Python: {python_executable}")
    else:
        python_executable = find_best_python(roots)
        if python_executable is not None:
            lines.append(f"Auto-detected ComfyUI Python: {python_executable}")

    ok, message = deploy_fn(custom_nodes_path, force=force)
    lines.append(f"Deployment: {message}")
    if not ok:
        return RunbookReport(False, lines, custom_nodes_path=custom_nodes_path, python_executable=python_executable)

    ok, message = verify_fn(custom_nodes_path)
    lines.append(f"Direct verification: {message}")
    if not ok:
        return RunbookReport(False, lines, custom_nodes_path=custom_nodes_path, python_executable=python_executable)

    if python_executable is not None:
        ok, message = verify_runtime_fn(custom_nodes_path, python_executable)
        lines.append(f"Runtime verification: {message}")
        if not ok:
            return RunbookReport(False, lines, custom_nodes_path=custom_nodes_path, python_executable=python_executable)

        if run_smoke:
            comfy_root = custom_nodes_path.parent
            live_keys_present = detect_live_keys_fn()
            smoke_report = smoke_check_fn(
                comfy_root=comfy_root,
                python_executable=python_executable,
                host=smoke_host,
                port=smoke_port,
                timeout=smoke_timeout,
            )
            for line in smoke_report.lines:
                lines.append(f"Registration smoke check: {line}")
            if not smoke_report.ok:
                return RunbookReport(False, lines, custom_nodes_path=custom_nodes_path, python_executable=python_executable)

            workflow_checks = [
                ("Text workflow smoke check", workflow_smoke.DEFAULT_TEXT_WORKFLOW_PATH),
                ("Image workflow smoke check", workflow_smoke.DEFAULT_IMAGE_WORKFLOW_PATH),
            ]
            workflow_reports = multi_workflow_smoke_fn(
                [path for _, path in workflow_checks],
                comfy_root,
                python_executable,
                smoke_host,
                smoke_port,
                smoke_timeout,
                verify_saved_images=live_keys_present,
            )
            for (label, _workflow_path), workflow_report in zip(workflow_checks, workflow_reports):
                for line in workflow_report.lines:
                    lines.append(f"{label}: {line}")
                if not workflow_report.ok:
                    return RunbookReport(False, lines, custom_nodes_path=custom_nodes_path, python_executable=python_executable)

            if live_keys_present:
                try:
                    live_report = live_smoke_fn(comfy_root, python_executable, smoke_host, smoke_port)
                except Exception as error:
                    lines.append(f"Live ComfyUI smoke: unavailable: {error}")
                    return RunbookReport(False, lines, custom_nodes_path=custom_nodes_path, python_executable=python_executable)
                if hasattr(live_report, "lines") and hasattr(live_report, "ok"):
                    for line in live_report.lines:
                        lines.append(f"Live ComfyUI smoke: {line}")
                    if not live_report.ok:
                        return RunbookReport(False, lines, custom_nodes_path=custom_nodes_path, python_executable=python_executable)
                elif isinstance(live_report, dict):
                    image_count = len(live_report.get("images", [])) if isinstance(live_report.get("images"), list) else 0
                    prompt_id = live_report.get("prompt_id", "<unknown>")
                    lines.append(f"Live ComfyUI smoke: saved {image_count} image(s) for prompt {prompt_id}")
                else:
                    lines.append("Live ComfyUI smoke: completed.")
            else:
                lines.append("Live ComfyUI smoke: skipped because no Nanaix API key is configured.")
        else:
            lines.append("Registration smoke check: skipped by option.")
    else:
        lines.append("Runtime verification: skipped because no ComfyUI Python executable was found.")

    lines.append("Runbook completed successfully.")
    return RunbookReport(True, lines, custom_nodes_path=custom_nodes_path, python_executable=python_executable)


def main() -> int:
    args = parse_args()
    roots = [Path(root) for root in args.roots]
    report = execute(
        custom_nodes=args.custom_nodes,
        comfy_python=args.python,
        roots=roots,
        force=args.force,
        smoke_host=args.smoke_host,
        smoke_port=args.smoke_port,
        smoke_timeout=args.smoke_timeout,
        run_smoke=not args.skip_smoke,
    )
    print(report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
