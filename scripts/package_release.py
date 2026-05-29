from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.common import IGNORE_NAMES, PLUGIN_NAME
from scripts.install_to_comfyui import copy_plugin_tree
from scripts.verify_install import verify_install, verify_install_runtime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a clean release zip for the Nanaix ComfyUI plugin.")
    parser.add_argument("--output-dir", required=True, help="Directory where the zip file will be written")
    parser.add_argument("--name", default=PLUGIN_NAME, help="Base name for the zip archive")
    parser.add_argument(
        "--python",
        default="",
        help="Optional ComfyUI Python executable. When provided, archive verification runs inside that Python runtime.",
    )
    return parser.parse_args()


def create_release_zip(output_dir: Path, archive_name: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filtered_base = output_dir / f"{archive_name}_clean"
    temp_dir = output_dir / f".{archive_name}_staging"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    copy_plugin_tree(ROOT, temp_dir / PLUGIN_NAME)
    clean_archive = shutil.make_archive(
        str(filtered_base),
        "zip",
        root_dir=temp_dir,
        base_dir=PLUGIN_NAME,
        logger=None,
    )
    shutil.rmtree(temp_dir)
    final_path = output_dir / f"{archive_name}.zip"
    if final_path.exists():
        final_path.unlink()
    Path(clean_archive).rename(final_path)
    return final_path


def verify_release_archive(archive_path: Path, python_executable: Path | None = None) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        temp_root = Path(tmp)
        custom_nodes = temp_root / "custom_nodes"
        custom_nodes.mkdir(parents=True)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(custom_nodes)
        if python_executable is not None:
            return verify_install_runtime(custom_nodes, python_executable=python_executable)
        return verify_install(custom_nodes)


def main() -> int:
    args = parse_args()
    archive_path = create_release_zip(Path(args.output_dir).resolve(), args.name)
    print(f"Created release archive at {archive_path}")
    python_executable = Path(args.python).resolve() if args.python.strip() else None
    ok, message = verify_release_archive(archive_path, python_executable=python_executable)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
