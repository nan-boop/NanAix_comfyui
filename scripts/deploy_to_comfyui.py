from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import doctor, find_comfyui, install_to_comfyui, live_comfy_smoke, verify_install


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install and verify the Nanaix plugin in a ComfyUI custom_nodes directory.")
    parser.add_argument(
        "--custom-nodes",
        default="",
        help="Path to the ComfyUI custom_nodes directory. If omitted, the script will try to find the best candidate automatically.",
    )
    parser.add_argument(
        "--roots",
        nargs="*",
        default=[str(root) for root in find_comfyui.DEFAULT_ROOTS],
        help="Optional roots to scan when --custom-nodes is omitted.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing installation")
    parser.add_argument(
        "--python",
        default="",
        help="Optional ComfyUI Python executable. When provided, post-deploy verification runs inside that Python runtime.",
    )
    return parser.parse_args()


def find_best_comfy_python(roots: list[Path], limit: int = 20) -> Path | None:
    return find_comfyui.find_best_comfy_python_candidate(roots, limit=limit)


def resolve_custom_nodes_path(custom_nodes: str, roots: list[Path] | None = None) -> Path:
    if custom_nodes.strip():
        return Path(custom_nodes).resolve()

    search_roots = roots or find_comfyui.DEFAULT_ROOTS
    candidate = find_comfyui.find_best_custom_nodes_candidate(search_roots)
    if candidate is None:
        raise ValueError("No ComfyUI custom_nodes directory found automatically. Pass --custom-nodes explicitly.")
    return candidate.resolve()


def remove_tree(path: Path) -> None:
    if not path.exists():
        return

    attempts = 2
    for attempt in range(1, attempts + 1):
        try:
            shutil.rmtree(path)
            return
        except OSError:
            if attempt >= attempts:
                raise
            time.sleep(0.1)


def deploy(custom_nodes_path: Path, force: bool = False, python_executable: Path | None = None) -> tuple[bool, str]:
    install_to_comfyui.validate_custom_nodes_path(custom_nodes_path)
    destination = custom_nodes_path / install_to_comfyui.PLUGIN_NAME
    if destination.exists() and not force:
        return False, f"Destination already exists: {destination}. Re-run with --force to overwrite."

    backup_dir: Path | None = None
    if destination.exists():
        backup_dir = custom_nodes_path / f".{install_to_comfyui.PLUGIN_NAME}_backup"
        if backup_dir.exists():
            remove_tree(backup_dir)
        shutil.copytree(destination, backup_dir)

    try:
        install_to_comfyui.copy_plugin_tree(install_to_comfyui.ROOT, destination)
        if python_executable is not None:
            ok, message = verify_install.verify_install_runtime(custom_nodes_path, python_executable=python_executable)
        else:
            ok, message = verify_install.verify_install(custom_nodes_path)
        if ok:
            if backup_dir and backup_dir.exists():
                remove_tree(backup_dir)
            return ok, message

        if backup_dir and backup_dir.exists():
            if destination.exists():
                remove_tree(destination)
            shutil.copytree(backup_dir, destination)
            remove_tree(backup_dir)
            return False, f"{message}. Previous installation was restored."
        return ok, message
    except Exception as error:
        if backup_dir and backup_dir.exists():
            if destination.exists():
                remove_tree(destination)
            shutil.copytree(backup_dir, destination)
            remove_tree(backup_dir)
            return False, f"Deployment failed and previous installation was restored: {error}"
        raise


def collect_deploy_self_check_lines() -> list[str]:
    image2_key, banana_key = live_comfy_smoke.resolve_live_keys("", "")
    return doctor.collect_provider_model_visibility(image2_api_key=image2_key, banana_api_key=banana_key)


def main() -> int:
    args = parse_args()
    roots = [Path(root) for root in args.roots]
    custom_nodes_path = resolve_custom_nodes_path(args.custom_nodes, roots=roots)
    python_executable = Path(args.python).resolve() if args.python.strip() else find_best_comfy_python(roots)
    try:
        for line in collect_deploy_self_check_lines():
            print(f"Doctor self-check: {line}")
    except Exception as error:
        print(f"Doctor self-check: unavailable: {error}")
    ok, message = deploy(custom_nodes_path, force=args.force, python_executable=python_executable)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
