from __future__ import annotations

from pathlib import Path

import importlib
import sys


def test_package_exports_web_directory() -> None:
    root = Path(__file__).resolve().parents[1]
    parent = root.parent
    added = False
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
        added = True

    try:
        module = importlib.import_module(root.name)
        assert getattr(module, "WEB_DIRECTORY", None) == "./web"
    finally:
        if added:
            sys.path.remove(str(parent))
        for key in list(sys.modules):
            if key == root.name or key.startswith(f"{root.name}."):
                sys.modules.pop(key, None)


def test_node_docs_exist_for_both_nodes() -> None:
    docs_root = Path(__file__).resolve().parents[1] / "web" / "docs"
    assert (docs_root / "Nanaix_Text.md").exists()
    assert (docs_root / "Nanaix_Image.md").exists()


def test_node_docs_call_out_key_selection_and_reference_requirements() -> None:
    docs_root = Path(__file__).resolve().parents[1] / "web" / "docs"
    text_doc = (docs_root / "Nanaix_Text.md").read_text(encoding="utf-8")
    image_doc = (docs_root / "Nanaix_Image.md").read_text(encoding="utf-8")

    assert "Use the single visible `api_key` field for the selected model" in text_doc
    assert "Connect at least one image input before queueing the workflow" in image_doc
    assert "Successful runs save the current keys and common parameters" in text_doc


def test_node_docs_explain_resolution_presets_and_saved_key_behavior() -> None:
    docs_root = Path(__file__).resolve().parents[1] / "web" / "docs"
    text_doc = (docs_root / "Nanaix_Text.md").read_text(encoding="utf-8")
    image_doc = (docs_root / "Nanaix_Image.md").read_text(encoding="utf-8")

    assert "resolution_preset" in text_doc
    assert "square -> 1024x1024" in text_doc
    assert "landscape_hd -> 1536x1024" in text_doc
    assert "portrait_2k -> 1024x2048" in image_doc
    assert "leaving the visible key blank still raises an error" in text_doc
    assert "leaving the visible key blank still raises an error" in image_doc


def test_node_docs_explain_batch_output_compatibility() -> None:
    docs_root = Path(__file__).resolve().parents[1] / "web" / "docs"
    text_doc = (docs_root / "Nanaix_Text.md").read_text(encoding="utf-8")
    image_doc = (docs_root / "Nanaix_Image.md").read_text(encoding="utf-8")

    assert "When `n > 1`, the node returns an image batch" in text_doc
    assert "`PreviewImage` and `SaveImage`" in text_doc
    assert "When `n > 1`, the node returns an image batch" in image_doc
    assert "`PreviewImage` and `SaveImage`" in image_doc
