from __future__ import annotations

import json
from pathlib import Path


def test_example_workflows_are_valid_json_and_reference_expected_nodes() -> None:
    base = Path(__file__).resolve().parents[1] / "examples"

    text_workflow = json.loads((base / "minimal_text_workflow.json").read_text(encoding="utf-8"))
    image_workflow = json.loads((base / "minimal_image_workflow.json").read_text(encoding="utf-8"))
    multi_image_workflow = json.loads((base / "minimal_multi_image_workflow.json").read_text(encoding="utf-8"))

    assert any(node["type"] == "Nanaix_Text" for node in text_workflow["nodes"])
    assert any(node["type"] == "PreviewImage" for node in text_workflow["nodes"])
    assert any(node["type"] == "SaveImage" for node in text_workflow["nodes"])

    assert any(node["type"] == "Nanaix_Image" for node in image_workflow["nodes"])
    assert any(node["type"] == "PreviewImage" for node in image_workflow["nodes"])
    assert any(node["type"] == "SaveImage" for node in image_workflow["nodes"])

    assert any(node["type"] == "Nanaix_Image" for node in multi_image_workflow["nodes"])
    assert any(node["type"] == "PreviewImage" for node in multi_image_workflow["nodes"])
    assert any(node["type"] == "SaveImage" for node in multi_image_workflow["nodes"])
    assert sum(1 for node in multi_image_workflow["nodes"] if node["type"] == "LoadImage") == 2
