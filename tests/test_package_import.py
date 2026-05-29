from __future__ import annotations

import importlib
import sys
from pathlib import Path


def test_package_import_exposes_comfy_mappings() -> None:
    root = Path(__file__).resolve().parents[1]
    parent = root.parent
    added = False
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
        added = True

    try:
        module = importlib.import_module(root.name)
        assert hasattr(module, "NODE_CLASS_MAPPINGS")
        assert sorted(module.NODE_CLASS_MAPPINGS.keys()) == ["Nanaix_Image", "Nanaix_Text"]
    finally:
        if added:
            sys.path.remove(str(parent))
