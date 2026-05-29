from __future__ import annotations

import argparse
import tempfile
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import find_comfyui
from scripts.common import IGNORE_NAMES, PLUGIN_NAME, RUNTIME_INCLUDE_NAMES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install this plugin into a ComfyUI custom_nodes directory.")
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
    return parser.parse_args()


def validate_custom_nodes_path(path: Path) -> None:
    if path.name != "custom_nodes":
        raise ValueError(f"Expected a custom_nodes directory, got: {path}")

    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise ValueError(f"Target path is not a directory: {path}")


def copy_plugin_tree(source: Path, destination: Path) -> None:
    preserved_config: str | None = None
    config_path = destination / "nanaix_config.json"
    if config_path.exists():
        preserved_config = config_path.read_text(encoding="utf-8")

    if destination.exists():
        shutil.rmtree(destination)

    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        if child.name not in RUNTIME_INCLUDE_NAMES or child.name in IGNORE_NAMES:
            continue
        target = destination / child.name
        if child.is_dir():
            shutil.copytree(child, target, ignore=shutil.ignore_patterns(*IGNORE_NAMES))
        else:
            shutil.copy2(child, target)

    if preserved_config is not None:
        (destination / "nanaix_config.json").write_text(preserved_config, encoding="utf-8")


def main() -> int:
    args = parse_args()
    roots = [Path(root) for root in args.roots]
    auto_detected = False
    if args.custom_nodes.strip():
        custom_nodes_path = Path(args.custom_nodes).resolve()
    else:
        candidate = find_comfyui.find_best_custom_nodes_candidate(roots)
        if candidate is None:
            raise ValueError("No ComfyUI custom_nodes directory found automatically. Pass --custom-nodes explicitly.")
        custom_nodes_path = candidate.resolve()
        auto_detected = True
    validate_custom_nodes_path(custom_nodes_path)

    destination = custom_nodes_path / PLUGIN_NAME
    if destination.exists() and not args.force:
        raise ValueError(f"Destination already exists: {destination}. Re-run with --force to overwrite.")

    if auto_detected:
        print(f"Auto-detected custom_nodes: {custom_nodes_path}")
    copy_plugin_tree(ROOT, destination)
    print(f"Installed {PLUGIN_NAME} to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
