from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugin_info import PLUGIN_NAME, PLUGIN_VERSION

EXPECTED_NODES = {"Nanaix_Text", "Nanaix_Image"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify that the Nanaix plugin is importable from a ComfyUI custom_nodes directory.")
    parser.add_argument("--custom-nodes", required=True, help="Path to the ComfyUI custom_nodes directory")
    parser.add_argument(
        "--python",
        default="",
        help="Optional ComfyUI Python executable. When provided, verification runs inside that Python runtime.",
    )
    return parser.parse_args()


def purge_plugin_modules() -> None:
    to_delete = [name for name in sys.modules if name == PLUGIN_NAME or name.startswith(f"{PLUGIN_NAME}.")]
    for name in to_delete:
        sys.modules.pop(name, None)


def validate_custom_nodes_path(custom_nodes_path: Path) -> tuple[bool, str]:
    if custom_nodes_path.name != "custom_nodes":
        return False, f"Expected a custom_nodes directory, got: {custom_nodes_path}"

    if not custom_nodes_path.exists():
        return False, f"custom_nodes directory does not exist: {custom_nodes_path}"

    return True, ""


def verify_install(custom_nodes_path: Path) -> tuple[bool, str]:
    ok, message = validate_custom_nodes_path(custom_nodes_path)
    if not ok:
        return ok, message

    sys.path.insert(0, str(custom_nodes_path))
    try:
        purge_plugin_modules()
        module = importlib.import_module(PLUGIN_NAME)
        mappings = getattr(module, "NODE_CLASS_MAPPINGS", {})
        node_names = set(mappings.keys())
        missing = EXPECTED_NODES - node_names
        if missing:
            return False, f"Missing expected nodes: {', '.join(sorted(missing))}"
        version = getattr(module, "__version__", PLUGIN_VERSION)
        return True, f"Verified {PLUGIN_NAME} v{version}: {', '.join(sorted(node_names))}"
    except Exception as error:
        return False, f"Failed to import {PLUGIN_NAME}: {error}"
    finally:
        sys.path.remove(str(custom_nodes_path))
        purge_plugin_modules()


def build_runtime_probe_script(custom_nodes_path: Path) -> str:
    expected_nodes_json = json.dumps(sorted(EXPECTED_NODES))
    custom_nodes_json = json.dumps(str(custom_nodes_path.resolve()))
    plugin_name_json = json.dumps(PLUGIN_NAME)
    plugin_version_json = json.dumps(PLUGIN_VERSION)
    return f"""
import importlib
import json
import sys

EXPECTED_NODES = set(json.loads({expected_nodes_json!r}))
CUSTOM_NODES = json.loads({custom_nodes_json!r})
PLUGIN_NAME = json.loads({plugin_name_json!r})
PLUGIN_VERSION = json.loads({plugin_version_json!r})

sys.path.insert(0, CUSTOM_NODES)
try:
    module = importlib.import_module(PLUGIN_NAME)
    mappings = getattr(module, "NODE_CLASS_MAPPINGS", {{}})
    node_names = set(mappings.keys())
    missing = EXPECTED_NODES - node_names
    if missing:
        raise SystemExit(f"Missing expected nodes: {{', '.join(sorted(missing))}}")
    version = getattr(module, "__version__", PLUGIN_VERSION)
    print(f"Verified {{PLUGIN_NAME}} v{{version}}: {{', '.join(sorted(node_names))}}")
finally:
    if CUSTOM_NODES in sys.path:
        sys.path.remove(CUSTOM_NODES)
""".strip()


def verify_install_runtime(custom_nodes_path: Path, python_executable: Path) -> tuple[bool, str]:
    ok, message = validate_custom_nodes_path(custom_nodes_path)
    if not ok:
        return ok, message

    if not python_executable.exists():
        return False, f"Python executable does not exist: {python_executable}"

    command = [str(python_executable), "-c", build_runtime_probe_script(custom_nodes_path)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        return False, f"Failed to start Python executable {python_executable}: {error}"
    output = (result.stdout or "").strip()
    error_output = (result.stderr or "").strip()
    if result.returncode == 0:
        return True, output or f"Verified {PLUGIN_NAME} using runtime {python_executable}"

    combined = error_output or output or f"Runtime verification failed with exit code {result.returncode}"
    return False, combined


def main() -> int:
    args = parse_args()
    custom_nodes_path = Path(args.custom_nodes).resolve()
    if args.python.strip():
        ok, message = verify_install_runtime(custom_nodes_path, python_executable=Path(args.python))
    else:
        ok, message = verify_install(custom_nodes_path)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
