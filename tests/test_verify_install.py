from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts import verify_install


def test_verify_install_rejects_non_custom_nodes_path(tmp_path: Path) -> None:
    ok, message = verify_install.verify_install(tmp_path / "plugins")

    assert not ok
    assert "Expected a custom_nodes directory" in message


def test_verify_install_reports_missing_directory(tmp_path: Path) -> None:
    ok, message = verify_install.verify_install(tmp_path / "custom_nodes")

    assert not ok
    assert "does not exist" in message


def test_verify_install_accepts_valid_plugin_layout(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "custom_nodes"
    plugin_dir = custom_nodes / "nanaix_Comfy"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "__init__.py").write_text(
        '__version__ = "0.1.0"\nNODE_CLASS_MAPPINGS = {"Nanaix_Text": object(), "Nanaix_Image": object()}\n',
        encoding="utf-8",
    )

    ok, message = verify_install.verify_install(custom_nodes)

    assert ok
    assert "Nanaix_Text" in message
    assert "v0.1.0" in message


def test_verify_install_does_not_reuse_cached_submodules_between_layouts(tmp_path: Path) -> None:
    custom_nodes_a = tmp_path / "a" / "custom_nodes"
    plugin_dir_a = custom_nodes_a / "nanaix_Comfy"
    (plugin_dir_a / "nodes").mkdir(parents=True)
    (plugin_dir_a / "__init__.py").write_text(
        '__version__ = "0.1.0"\nfrom .nodes.example import NODE_CLASS_MAPPINGS\n',
        encoding="utf-8",
    )
    (plugin_dir_a / "nodes" / "example.py").write_text(
        'NODE_CLASS_MAPPINGS = {"Nanaix_Text": object(), "Nanaix_Image": object()}\n',
        encoding="utf-8",
    )

    ok_a, _ = verify_install.verify_install(custom_nodes_a)

    custom_nodes_b = tmp_path / "b" / "custom_nodes"
    plugin_dir_b = custom_nodes_b / "nanaix_Comfy"
    (plugin_dir_b / "nodes").mkdir(parents=True)
    (plugin_dir_b / "__init__.py").write_text(
        '__version__ = "0.1.0"\nfrom .nodes.example import NODE_CLASS_MAPPINGS\n',
        encoding="utf-8",
    )
    (plugin_dir_b / "nodes" / "example.py").write_text(
        'NODE_CLASS_MAPPINGS = {"Nanaix_Text": object()}\n',
        encoding="utf-8",
    )

    ok_b, message_b = verify_install.verify_install(custom_nodes_b)

    assert ok_a
    assert not ok_b
    assert "Missing expected nodes" in message_b


def test_build_runtime_probe_script_mentions_expected_nodes_and_module_path(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "custom_nodes"
    script = verify_install.build_runtime_probe_script(custom_nodes)

    assert "Nanaix_Text" in script
    assert "Nanaix_Image" in script
    assert "CUSTOM_NODES = json.loads(" in script
    assert custom_nodes.name in script


def test_verify_install_runtime_invokes_supplied_python(monkeypatch, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "custom_nodes"
    plugin_dir = custom_nodes / "nanaix_Comfy"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "__init__.py").write_text(
        '__version__ = "0.1.0"\nNODE_CLASS_MAPPINGS = {"Nanaix_Text": object(), "Nanaix_Image": object()}\n',
        encoding="utf-8",
    )
    python_executable = tmp_path / "python.exe"
    python_executable.write_text("", encoding="utf-8")

    calls: list[list[str]] = []

    def fake_run(command, capture_output, text, check):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="runtime ok\n", stderr="")

    monkeypatch.setattr(verify_install.subprocess, "run", fake_run)

    ok, message = verify_install.verify_install_runtime(custom_nodes, python_executable=python_executable)

    assert ok
    assert message == "runtime ok"
    assert calls[0][:2] == [str(python_executable), "-c"]


def test_verify_install_runtime_surfaces_python_failure_output(monkeypatch, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "custom_nodes"
    custom_nodes.mkdir(parents=True)
    python_executable = tmp_path / "python.exe"
    python_executable.write_text("", encoding="utf-8")

    def fake_run(command, capture_output, text, check):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="boom")

    monkeypatch.setattr(verify_install.subprocess, "run", fake_run)

    ok, message = verify_install.verify_install_runtime(custom_nodes, python_executable=python_executable)

    assert not ok
    assert "boom" in message


def test_verify_install_runtime_reports_missing_python_executable(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "custom_nodes"
    custom_nodes.mkdir(parents=True)

    ok, message = verify_install.verify_install_runtime(
        custom_nodes,
        python_executable=tmp_path / "missing-python.exe",
    )

    assert not ok
    assert "Python executable does not exist" in message
    assert "missing-python.exe" in message
