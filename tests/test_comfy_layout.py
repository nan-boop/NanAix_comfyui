from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path


def test_package_imports_from_comfy_custom_nodes_layout(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[1]
    comfy_root = tmp_path / "ComfyUI"
    custom_nodes = comfy_root / "custom_nodes"
    custom_nodes.mkdir(parents=True)

    destination = custom_nodes / "nanaix_Comfy"
    shutil.copytree(
        source_root,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".hypothesis"),
    )

    sys.path.insert(0, str(custom_nodes))
    try:
        module = importlib.import_module("nanaix_Comfy")
        assert sorted(module.NODE_CLASS_MAPPINGS.keys()) == ["Nanaix_Image", "Nanaix_Text"]
        assert module.NODE_DISPLAY_NAME_MAPPINGS["Nanaix_Text"] == "Nanaix_Text"
    finally:
        sys.path.remove(str(custom_nodes))
        sys.modules.pop("nanaix_Comfy", None)
