from __future__ import annotations

import tomllib
from pathlib import Path


def test_pyproject_toml_is_parseable_and_matches_runtime_version() -> None:
    root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    plugin_info: dict[str, object] = {}
    exec((root / "plugin_info.py").read_text(encoding="utf-8"), plugin_info)

    assert pyproject["project"]["version"] == plugin_info["PLUGIN_VERSION"]
    assert pyproject["tool"]["comfy"]["DisplayName"] == "Nanaix Image Nodes"


def test_comfyignore_excludes_dev_only_paths() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / ".comfyignore").read_text(encoding="utf-8")

    assert "docs/" in content
    assert "tests/" in content
