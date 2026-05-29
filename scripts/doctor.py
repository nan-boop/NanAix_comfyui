from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugin_info import PLUGIN_NAME, PLUGIN_VERSION, SUPPORTED_MODELS
from services.banana_client import BananaClient
from services.image2_client import Image2Client
from scripts.find_comfyui import DEFAULT_ROOTS, find_custom_nodes_candidates, find_matching_python_for_custom_nodes
from scripts.verify_install import verify_install, verify_install_runtime


DEPENDENCIES = ["numpy", "PIL", "torch"]
IMAGE2_KEY_ENV = "NANAIX_IMAGE2_API_KEY"
BANANA_KEY_ENV = "NANAIX_BANANA_API_KEY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect Nanaix plugin readiness and local ComfyUI integration clues.")
    parser.add_argument("--custom-nodes", default="", help="Optional custom_nodes path to verify directly")
    parser.add_argument(
        "--python",
        default="",
        help="Optional ComfyUI Python executable. When provided with --custom-nodes, runtime verification uses this Python directly.",
    )
    parser.add_argument(
        "--roots",
        nargs="*",
        default=[str(root) for root in DEFAULT_ROOTS],
        help="Optional roots to scan for custom_nodes candidates.",
    )
    parser.add_argument("--limit", type=int, default=5, help="Maximum number of discovered custom_nodes paths to print")
    return parser.parse_args()


def collect_dependency_status() -> dict[str, bool]:
    return {name: importlib.util.find_spec(name) is not None for name in DEPENDENCIES}


def collect_provider_model_visibility(image2_api_key: str = "", banana_api_key: str = "") -> list[str]:
    lines: list[str] = []

    if image2_api_key:
        try:
            models = Image2Client(image2_api_key).list_models(node_name="Doctor")
        except Exception as error:
            lines.append(f"image-2: FAIL - {error}")
        else:
            if "gpt-image-2" in models:
                lines.append(f"image-2: OK - visible models: {', '.join(models)}")
            else:
                visible = ", ".join(models) if models else "none"
                lines.append(f"image-2: FAIL - gpt-image-2 is not visible for this key (visible: {visible})")
                lines.append(
                    "image-2: next step - check whether this key belongs to the Nanaix image group, then retry GET /models."
                )
    else:
        lines.append(f"image-2: skipped (set {IMAGE2_KEY_ENV} to verify /models visibility)")

    if banana_api_key:
        try:
            models = BananaClient(banana_api_key).list_models(node_name="Doctor")
        except Exception as error:
            lines.append(f"nano-banana: FAIL - {error}")
        else:
            missing_models = [model for model in ("nano-banana-2", "nano-banana-pro") if model not in models]
            if missing_models:
                visible = ", ".join(models) if models else "none"
                lines.append(
                    f"nano-banana: FAIL - missing expected models: {', '.join(missing_models)} (visible: {visible})"
                )
                lines.append(
                    "nano-banana: next step - confirm that this key is attached to a nano-banana-enabled account group."
                )
            else:
                lines.append(f"nano-banana: OK - visible models: {', '.join(models)}")
    else:
        lines.append(f"nano-banana: skipped (set {BANANA_KEY_ENV} to verify configured model visibility)")

    return lines


def build_report(custom_nodes: str = "", python: str = "", limit: int = 5, roots: list[Path] | None = None) -> str:
    candidates: list[Path] = []
    lines = [
        f"Plugin: {PLUGIN_NAME}",
        f"Version: {PLUGIN_VERSION}",
        f"Supported models: {', '.join(SUPPORTED_MODELS)}",
        "",
        "Dependency status:",
    ]

    for name, available in collect_dependency_status().items():
        lines.append(f"- {name}: {'OK' if available else 'MISSING'}")

    lines.append("")
    lines.append("Discovered custom_nodes candidates:")
    if custom_nodes:
        lines.append("- skipped because --custom-nodes was provided")
    else:
        candidates = find_custom_nodes_candidates(roots or DEFAULT_ROOTS, limit=limit)
        if candidates:
            for candidate in candidates:
                python_candidate = find_matching_python_for_custom_nodes(candidate, limit=limit)
                python_text = str(python_candidate) if python_candidate is not None else "none"
                lines.append(f"- custom_nodes={candidate} | python={python_text}")
        else:
            lines.append("- none found")

    lines.append("")
    lines.append("Provider self-check:")
    for line in collect_provider_model_visibility(
        image2_api_key=os.environ.get(IMAGE2_KEY_ENV, ""),
        banana_api_key=os.environ.get(BANANA_KEY_ENV, ""),
    ):
        lines.append(f"- {line}")

    if custom_nodes:
        resolved_custom_nodes = Path(custom_nodes).resolve()
        ok, message = verify_install(resolved_custom_nodes)
        lines.append("")
        lines.append("Direct verification:")
        lines.append(f"- {'OK' if ok else 'FAIL'}: {message}")
        if not ok:
            lines.append("- Hint: run deploy_to_comfyui.py first if the plugin has not been installed into this custom_nodes directory yet.")
        else:
            python_candidate = Path(python).resolve() if python.strip() else find_matching_python_for_custom_nodes(resolved_custom_nodes, limit=limit)
            if python_candidate is not None:
                runtime_ok, runtime_message = verify_install_runtime(resolved_custom_nodes, python_candidate)
                lines.append("Runtime verification:")
                lines.append(f"- {'OK' if runtime_ok else 'FAIL'}: {runtime_message}")
    elif candidates:
        best_candidate = candidates[0].resolve()
        ok, message = verify_install(best_candidate)
        lines.append("")
        lines.append("Auto verification:")
        lines.append(f"- {'OK' if ok else 'FAIL'}: {message}")
        if ok:
            python_candidate = find_matching_python_for_custom_nodes(best_candidate, limit=limit)
            if python_candidate is not None:
                runtime_ok, runtime_message = verify_install_runtime(best_candidate, python_candidate)
                lines.append("Auto runtime verification:")
                lines.append(f"- {'OK' if runtime_ok else 'FAIL'}: {runtime_message}")

    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    roots = [Path(root) for root in args.roots]
    print(build_report(custom_nodes=args.custom_nodes, python=args.python, limit=args.limit, roots=roots))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
