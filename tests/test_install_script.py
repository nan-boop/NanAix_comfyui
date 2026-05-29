from __future__ import annotations

import sys
from pathlib import Path

from scripts import install_to_comfyui
from scripts import verify_install


def test_validate_custom_nodes_path_rejects_wrong_directory_name(tmp_path: Path) -> None:
    wrong_path = tmp_path / "plugins"

    try:
        install_to_comfyui.validate_custom_nodes_path(wrong_path)
    except ValueError as error:
        assert "Expected a custom_nodes directory" in str(error)
    else:
        raise AssertionError("expected ValueError for non-custom_nodes path")


def test_copy_plugin_tree_ignores_cache_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".comfyignore").write_text("tests/\n", encoding="utf-8")
    (source / "__init__.py").write_text("ok", encoding="utf-8")
    (source / "plugin_info.py").write_text("PLUGIN_VERSION = '0.1.0'\n", encoding="utf-8")
    (source / "pyproject.toml").write_text("[project]\nname='example'\nversion='0.1.0'\n", encoding="utf-8")
    (source / "README.md").write_text("readme", encoding="utf-8")
    (source / "requirements.txt").write_text("Pillow>=9.0.0\n", encoding="utf-8")
    (source / "nodes").mkdir()
    (source / "nodes" / "__init__.py").write_text("ok", encoding="utf-8")
    (source / "scripts").mkdir()
    (source / "scripts" / "tool.py").write_text("ok", encoding="utf-8")
    (source / "tests").mkdir()
    (source / "tests" / "temp.py").write_text("x", encoding="utf-8")
    (source / "docs").mkdir()
    (source / "docs" / "temp.md").write_text("x", encoding="utf-8")
    (source / "__pycache__").mkdir()
    (source / "__pycache__" / "temp.pyc").write_text("x", encoding="utf-8")
    (source / ".pytest_cache").mkdir()
    (source / ".pytest_cache" / "temp").write_text("x", encoding="utf-8")
    destination = tmp_path / "custom_nodes" / "nanaix_Comfy"

    install_to_comfyui.copy_plugin_tree(source, destination)

    assert (destination / "__init__.py").exists()
    assert (destination / ".comfyignore").exists()
    assert (destination / "plugin_info.py").exists()
    assert (destination / "pyproject.toml").exists()
    assert (destination / "README.md").exists()
    assert (destination / "requirements.txt").exists()
    assert (destination / "nodes" / "__init__.py").exists()
    assert (destination / "scripts" / "tool.py").exists()
    assert not (destination / "__pycache__").exists()
    assert not (destination / ".pytest_cache").exists()
    assert not (destination / "tests").exists()
    assert not (destination / "docs").exists()


def test_install_main_copies_into_custom_nodes(monkeypatch, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    monkeypatch.setattr(
        "sys.argv",
        [
            "install_to_comfyui.py",
            "--custom-nodes",
            str(custom_nodes),
        ],
    )
    monkeypatch.setattr(install_to_comfyui, "ROOT", tmp_path / "plugin")
    install_to_comfyui.ROOT.mkdir()
    (install_to_comfyui.ROOT / "__init__.py").write_text("ok", encoding="utf-8")

    exit_code = install_to_comfyui.main()

    assert exit_code == 0
    assert (custom_nodes / "nanaix_Comfy" / "__init__.py").exists()


def test_install_main_auto_detects_custom_nodes_when_not_provided(monkeypatch, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "install_to_comfyui.py",
        ],
    )
    monkeypatch.setattr(install_to_comfyui, "ROOT", tmp_path / "plugin")
    install_to_comfyui.ROOT.mkdir()
    (install_to_comfyui.ROOT / "__init__.py").write_text("ok", encoding="utf-8")
    monkeypatch.setattr(
        install_to_comfyui.find_comfyui,
        "find_best_custom_nodes_candidate",
        lambda roots=None, limit=20: custom_nodes.resolve(),
    )

    exit_code = install_to_comfyui.main()

    assert exit_code == 0
    assert (custom_nodes / "nanaix_Comfy" / "__init__.py").exists()


def test_install_main_reports_auto_detected_custom_nodes(monkeypatch, capsys, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "install_to_comfyui.py",
        ],
    )
    monkeypatch.setattr(install_to_comfyui, "ROOT", tmp_path / "plugin")
    install_to_comfyui.ROOT.mkdir()
    (install_to_comfyui.ROOT / "__init__.py").write_text("ok", encoding="utf-8")
    monkeypatch.setattr(
        install_to_comfyui.find_comfyui,
        "find_best_custom_nodes_candidate",
        lambda roots=None, limit=20: custom_nodes.resolve(),
    )

    exit_code = install_to_comfyui.main()
    lines = capsys.readouterr().out.splitlines()

    assert exit_code == 0
    assert lines[0] == f"Auto-detected custom_nodes: {custom_nodes.resolve()}"
    assert lines[-1] == f"Installed nanaix_Comfy to {custom_nodes.resolve() / 'nanaix_Comfy'}"


def test_install_main_passes_roots_to_auto_detection(monkeypatch, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    search_root = tmp_path / "scan-root"
    calls: list[tuple[list[Path], int]] = []

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "install_to_comfyui.py",
            "--roots",
            str(search_root),
        ],
    )
    monkeypatch.setattr(install_to_comfyui, "ROOT", tmp_path / "plugin")
    install_to_comfyui.ROOT.mkdir()
    (install_to_comfyui.ROOT / "__init__.py").write_text("ok", encoding="utf-8")

    def find_best_stub(roots, limit=20):
        calls.append((roots, limit))
        return custom_nodes.resolve()

    monkeypatch.setattr(
        install_to_comfyui.find_comfyui,
        "find_best_custom_nodes_candidate",
        find_best_stub,
    )

    exit_code = install_to_comfyui.main()

    assert exit_code == 0
    assert calls == [([search_root], 20)]


def test_copy_plugin_tree_preserves_existing_saved_config(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "__init__.py").write_text("ok", encoding="utf-8")
    (source / "plugin_info.py").write_text("PLUGIN_VERSION = '0.1.0'\n", encoding="utf-8")
    (source / "pyproject.toml").write_text("[project]\nname='example'\nversion='0.1.0'\n", encoding="utf-8")
    (source / "README.md").write_text("readme", encoding="utf-8")
    (source / "requirements.txt").write_text("Pillow>=9.0.0\n", encoding="utf-8")

    destination = tmp_path / "custom_nodes" / "nanaix_Comfy"
    destination.mkdir(parents=True)
    (destination / "__init__.py").write_text("old", encoding="utf-8")
    (destination / "nanaix_config.json").write_text('{"image2_api_key":"saved"}', encoding="utf-8")

    install_to_comfyui.copy_plugin_tree(source, destination)

    assert (destination / "__init__.py").read_text(encoding="utf-8") == "ok"
    assert (destination / "nanaix_config.json").read_text(encoding="utf-8") == '{"image2_api_key":"saved"}'


def test_real_plugin_runtime_bundle_imports_after_install(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[1]
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    destination = custom_nodes / "nanaix_Comfy"

    install_to_comfyui.validate_custom_nodes_path(custom_nodes)
    install_to_comfyui.copy_plugin_tree(source_root, destination)

    ok, message = verify_install.verify_install(custom_nodes)

    assert ok
    assert "Nanaix_Text" in message
