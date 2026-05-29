from __future__ import annotations

import argparse
import errno
from pathlib import Path

from scripts import deploy_to_comfyui


def test_deploy_reports_existing_destination_without_force(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    custom_nodes.mkdir(parents=True)
    destination = custom_nodes / "nanaix_Comfy"
    destination.mkdir()

    ok, message = deploy_to_comfyui.deploy(custom_nodes, force=False)

    assert not ok
    assert "Destination already exists" in message


def test_deploy_installs_and_verifies_real_plugin(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"

    ok, message = deploy_to_comfyui.deploy(custom_nodes, force=True)

    assert ok
    assert "Nanaix_Text" in message


def test_deploy_uses_supplied_python_runtime_for_verification(monkeypatch, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    python_executable = tmp_path / "python" / "python.exe"
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")
    calls: list[tuple[Path, Path]] = []

    def verify_runtime_stub(custom_nodes_path: Path, python_executable: Path) -> tuple[bool, str]:
        calls.append((custom_nodes_path, python_executable))
        return True, "runtime verify ok"

    monkeypatch.setattr(
        deploy_to_comfyui.verify_install,
        "verify_install_runtime",
        verify_runtime_stub,
    )

    ok, message = deploy_to_comfyui.deploy(custom_nodes, force=True, python_executable=python_executable)

    assert ok
    assert message == "runtime verify ok"
    assert calls == [(custom_nodes, python_executable)]


def test_deploy_restores_previous_installation_if_verification_fails(monkeypatch, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    destination = custom_nodes / "nanaix_Comfy"
    destination.mkdir(parents=True)
    (destination / "__init__.py").write_text("old-version", encoding="utf-8")

    monkeypatch.setattr(
        deploy_to_comfyui.verify_install,
        "verify_install",
        lambda path: (False, "Missing expected nodes: Nanaix_Image"),
    )

    ok, message = deploy_to_comfyui.deploy(custom_nodes, force=True)

    assert not ok
    assert "Previous installation was restored" in message
    assert (destination / "__init__.py").read_text(encoding="utf-8") == "old-version"


def test_deploy_uses_force_remove_helper_for_backup_cleanup(monkeypatch, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    destination = custom_nodes / "nanaix_Comfy"
    destination.mkdir(parents=True)
    (destination / "__init__.py").write_text("old-version", encoding="utf-8")
    removed_paths: list[Path] = []

    monkeypatch.setattr(
        deploy_to_comfyui.verify_install,
        "verify_install",
        lambda path: (True, "Verified nanaix_Comfy v0.1.0"),
    )
    monkeypatch.setattr(
        deploy_to_comfyui,
        "remove_tree",
        lambda path: removed_paths.append(path),
    )

    ok, message = deploy_to_comfyui.deploy(custom_nodes, force=True)

    assert ok
    assert "Verified nanaix_Comfy v0.1.0" in message
    assert custom_nodes / ".nanaix_Comfy_backup" in removed_paths


def test_remove_tree_retries_on_transient_directory_not_empty(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "stubborn-dir"
    target.mkdir()
    calls = {"count": 0}

    def flaky_rmtree(path: Path) -> None:
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError(errno.ENOTEMPTY, "Directory not empty", str(path))

    sleeps: list[float] = []
    monkeypatch.setattr(deploy_to_comfyui.shutil, "rmtree", flaky_rmtree)
    monkeypatch.setattr(deploy_to_comfyui.time, "sleep", lambda seconds: sleeps.append(seconds))

    deploy_to_comfyui.remove_tree(target)

    assert calls["count"] == 2
    assert sleeps == [0.1]


def test_resolve_custom_nodes_path_uses_best_auto_detected_candidate(monkeypatch, tmp_path: Path) -> None:
    expected = tmp_path / "ComfyUI" / "custom_nodes"
    expected.mkdir(parents=True)

    monkeypatch.setattr(
        deploy_to_comfyui.find_comfyui,
        "find_best_custom_nodes_candidate",
        lambda roots=None, limit=20: expected.resolve(),
    )

    result = deploy_to_comfyui.resolve_custom_nodes_path("", roots=[tmp_path])

    assert result == expected.resolve()


def test_resolve_custom_nodes_path_errors_when_no_auto_detected_candidate(tmp_path: Path) -> None:
    try:
        deploy_to_comfyui.resolve_custom_nodes_path("", roots=[tmp_path])
    except ValueError as error:
        assert "No ComfyUI custom_nodes directory found automatically" in str(error)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected auto-detection to fail when no candidates exist")


def test_main_prints_doctor_self_check_lines_before_deploy_result(monkeypatch, capsys, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    custom_nodes.mkdir(parents=True)

    monkeypatch.setattr(
        deploy_to_comfyui,
        "parse_args",
        lambda: argparse.Namespace(custom_nodes=str(custom_nodes), roots=[str(tmp_path)], force=True, python=""),
    )
    monkeypatch.setattr(deploy_to_comfyui, "resolve_custom_nodes_path", lambda custom_nodes, roots=None: Path(custom_nodes).resolve())
    monkeypatch.setattr(
        deploy_to_comfyui,
        "collect_deploy_self_check_lines",
        lambda: ["image-2: skipped", "nano-banana: skipped"],
    )
    monkeypatch.setattr(
        deploy_to_comfyui,
        "deploy",
        lambda custom_nodes_path, force=False, python_executable=None: (True, "Verified nanaix_Comfy v0.1.0"),
    )

    exit_code = deploy_to_comfyui.main()

    assert exit_code == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "Doctor self-check: image-2: skipped"
    assert lines[1] == "Doctor self-check: nano-banana: skipped"
    assert lines[-1] == "Verified nanaix_Comfy v0.1.0"


def test_main_reports_unavailable_doctor_self_check_but_still_returns_deploy_status(monkeypatch, capsys, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    custom_nodes.mkdir(parents=True)

    monkeypatch.setattr(
        deploy_to_comfyui,
        "parse_args",
        lambda: argparse.Namespace(custom_nodes=str(custom_nodes), roots=[str(tmp_path)], force=True, python=""),
    )
    monkeypatch.setattr(deploy_to_comfyui, "resolve_custom_nodes_path", lambda custom_nodes, roots=None: Path(custom_nodes).resolve())
    monkeypatch.setattr(
        deploy_to_comfyui,
        "collect_deploy_self_check_lines",
        lambda: (_ for _ in ()).throw(RuntimeError("network down")),
    )
    monkeypatch.setattr(
        deploy_to_comfyui,
        "deploy",
        lambda custom_nodes_path, force=False, python_executable=None: (False, "deploy failed"),
    )

    exit_code = deploy_to_comfyui.main()

    assert exit_code == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "Doctor self-check: unavailable: network down"
    assert lines[-1] == "deploy failed"


def test_main_passes_optional_python_runtime_to_deploy(monkeypatch, capsys, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    custom_nodes.mkdir(parents=True)
    calls: list[tuple[Path, bool, Path | None]] = []

    monkeypatch.setattr(
        deploy_to_comfyui,
        "parse_args",
        lambda: argparse.Namespace(
            custom_nodes=str(custom_nodes),
            roots=[str(tmp_path)],
            force=True,
            python="C:/Comfy/python.exe",
        ),
    )
    monkeypatch.setattr(deploy_to_comfyui, "resolve_custom_nodes_path", lambda custom_nodes, roots=None: Path(custom_nodes).resolve())
    monkeypatch.setattr(deploy_to_comfyui, "collect_deploy_self_check_lines", lambda: [])

    def deploy_stub(custom_nodes_path: Path, force: bool = False, python_executable: Path | None = None) -> tuple[bool, str]:
        calls.append((custom_nodes_path, force, python_executable))
        return True, "runtime deploy ok"

    monkeypatch.setattr(deploy_to_comfyui, "deploy", deploy_stub)

    exit_code = deploy_to_comfyui.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert calls == [(custom_nodes.resolve(), True, Path("C:/Comfy/python.exe").resolve())]
    assert "runtime deploy ok" in output


def test_main_auto_detects_python_runtime_for_deploy(monkeypatch, capsys, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    custom_nodes.mkdir(parents=True)
    detected_python = tmp_path / "python" / "python.exe"
    calls: list[tuple[Path, bool, Path | None]] = []

    monkeypatch.setattr(
        deploy_to_comfyui,
        "parse_args",
        lambda: argparse.Namespace(
            custom_nodes=str(custom_nodes),
            roots=[str(tmp_path)],
            force=True,
            python="",
        ),
    )
    monkeypatch.setattr(deploy_to_comfyui, "resolve_custom_nodes_path", lambda custom_nodes, roots=None: Path(custom_nodes).resolve())
    monkeypatch.setattr(deploy_to_comfyui, "collect_deploy_self_check_lines", lambda: [])
    monkeypatch.setattr(
        deploy_to_comfyui.find_comfyui,
        "find_best_custom_nodes_candidate",
        lambda roots=None, limit=20: custom_nodes.resolve(),
    )
    monkeypatch.setattr(
        deploy_to_comfyui.find_comfyui,
        "find_best_comfy_python_candidate",
        lambda roots=None, limit=20: detected_python.resolve(),
        raising=False,
    )

    def deploy_stub(custom_nodes_path: Path, force: bool = False, python_executable: Path | None = None) -> tuple[bool, str]:
        calls.append((custom_nodes_path, force, python_executable))
        return True, "auto runtime deploy ok"

    monkeypatch.setattr(deploy_to_comfyui, "deploy", deploy_stub)

    exit_code = deploy_to_comfyui.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert calls == [(custom_nodes.resolve(), True, detected_python.resolve())]
    assert "auto runtime deploy ok" in output


def test_main_continues_without_runtime_when_auto_detect_finds_none(monkeypatch, capsys, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    custom_nodes.mkdir(parents=True)
    calls: list[tuple[Path, bool, Path | None]] = []

    monkeypatch.setattr(
        deploy_to_comfyui,
        "parse_args",
        lambda: argparse.Namespace(
            custom_nodes=str(custom_nodes),
            roots=[str(tmp_path)],
            force=True,
            python="",
        ),
    )
    monkeypatch.setattr(deploy_to_comfyui, "resolve_custom_nodes_path", lambda custom_nodes, roots=None: Path(custom_nodes).resolve())
    monkeypatch.setattr(deploy_to_comfyui, "collect_deploy_self_check_lines", lambda: [])
    monkeypatch.setattr(
        deploy_to_comfyui.find_comfyui,
        "find_best_comfy_python_candidate",
        lambda roots=None, limit=20: None,
        raising=False,
    )

    def deploy_stub(custom_nodes_path: Path, force: bool = False, python_executable: Path | None = None) -> tuple[bool, str]:
        calls.append((custom_nodes_path, force, python_executable))
        return True, "light deploy ok"

    monkeypatch.setattr(deploy_to_comfyui, "deploy", deploy_stub)

    exit_code = deploy_to_comfyui.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert calls == [(custom_nodes.resolve(), True, None)]
    assert "light deploy ok" in output
