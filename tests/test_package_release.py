from __future__ import annotations

import sys
import zipfile
from pathlib import Path

from scripts import package_release


def test_create_release_zip_creates_archive_without_cache_artifacts(monkeypatch, tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    (plugin_root / ".comfyignore").write_text("tests/\n", encoding="utf-8")
    (plugin_root / "__init__.py").write_text("ok", encoding="utf-8")
    (plugin_root / "plugin_info.py").write_text('PLUGIN_NAME = "nanaix_Comfy"\nPLUGIN_VERSION = "0.1.0"\n', encoding="utf-8")
    (plugin_root / "pyproject.toml").write_text("[project]\nname='example'\nversion='0.1.0'\n", encoding="utf-8")
    (plugin_root / "README.md").write_text("readme", encoding="utf-8")
    (plugin_root / "requirements.txt").write_text("Pillow>=9.0.0\n", encoding="utf-8")
    (plugin_root / "nodes").mkdir()
    (plugin_root / "nodes" / "__init__.py").write_text("ok", encoding="utf-8")
    (plugin_root / "scripts").mkdir()
    (plugin_root / "scripts" / "tool.py").write_text("ok", encoding="utf-8")
    (plugin_root / "tests").mkdir()
    (plugin_root / "tests" / "temp.py").write_text("x", encoding="utf-8")
    (plugin_root / "__pycache__").mkdir()
    (plugin_root / "__pycache__" / "temp.pyc").write_text("x", encoding="utf-8")

    monkeypatch.setattr(package_release, "ROOT", plugin_root)
    output_dir = tmp_path / "dist"

    archive_path = package_release.create_release_zip(output_dir, "nanaix_Comfy")

    assert archive_path.exists()
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        assert "nanaix_Comfy/.comfyignore" in names
        assert "nanaix_Comfy/__init__.py" in names
        assert "nanaix_Comfy/plugin_info.py" in names
        assert "nanaix_Comfy/pyproject.toml" in names
        assert "nanaix_Comfy/README.md" in names
        assert "nanaix_Comfy/requirements.txt" in names
        assert "nanaix_Comfy/nodes/__init__.py" in names
        assert "nanaix_Comfy/scripts/tool.py" in names
        assert "nanaix_Comfy/web/docs/Nanaix_Text.md" in names or "nanaix_Comfy/scripts/tool.py" in names
        assert all("__pycache__" not in name for name in names)
        assert all("/tests/" not in name for name in names)


def test_verify_release_archive_imports_packaged_plugin(monkeypatch, tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    (plugin_root / ".comfyignore").write_text("tests/\n", encoding="utf-8")
    (plugin_root / "__init__.py").write_text(
        'NODE_CLASS_MAPPINGS = {"Nanaix_Text": object(), "Nanaix_Image": object()}\n',
        encoding="utf-8",
    )
    (plugin_root / "plugin_info.py").write_text('PLUGIN_NAME = "nanaix_Comfy"\nPLUGIN_VERSION = "0.1.0"\n', encoding="utf-8")
    (plugin_root / "pyproject.toml").write_text("[project]\nname='example'\nversion='0.1.0'\n", encoding="utf-8")
    (plugin_root / "README.md").write_text("readme", encoding="utf-8")

    monkeypatch.setattr(package_release, "ROOT", plugin_root)
    output_dir = tmp_path / "dist"
    archive_path = package_release.create_release_zip(output_dir, "nanaix_Comfy")

    ok, message = package_release.verify_release_archive(archive_path)

    assert ok
    assert "Nanaix_Text" in message


def test_real_plugin_release_archive_imports_after_packaging(tmp_path: Path) -> None:
    output_dir = tmp_path / "dist"
    archive_path = package_release.create_release_zip(output_dir, "nanaix_Comfy_real")

    ok, message = package_release.verify_release_archive(archive_path)

    assert ok
    assert "Nanaix_Image" in message


def test_main_verifies_archive_after_packaging(monkeypatch, capsys, tmp_path: Path) -> None:
    archive_path = tmp_path / "dist" / "nanaix_Comfy.zip"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "package_release.py",
            "--output-dir",
            str(tmp_path / "dist"),
        ],
    )
    monkeypatch.setattr(package_release, "create_release_zip", lambda output_dir, archive_name: archive_path)
    monkeypatch.setattr(
        package_release,
        "verify_release_archive",
        lambda path, python_executable=None: (True, "Verified install for nanaix_Comfy"),
    )

    exit_code = package_release.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert f"Created release archive at {archive_path}" in output
    assert "Verified install for nanaix_Comfy" in output


def test_main_returns_non_zero_when_archive_verification_fails(monkeypatch, capsys, tmp_path: Path) -> None:
    archive_path = tmp_path / "dist" / "nanaix_Comfy.zip"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "package_release.py",
            "--output-dir",
            str(tmp_path / "dist"),
        ],
    )
    monkeypatch.setattr(package_release, "create_release_zip", lambda output_dir, archive_name: archive_path)
    monkeypatch.setattr(
        package_release,
        "verify_release_archive",
        lambda path, python_executable=None: (False, "Failed to import packaged plugin"),
    )

    exit_code = package_release.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert f"Created release archive at {archive_path}" in output
    assert "Failed to import packaged plugin" in output


def test_main_passes_optional_python_runtime_to_archive_verification(monkeypatch, capsys, tmp_path: Path) -> None:
    archive_path = tmp_path / "dist" / "nanaix_Comfy.zip"
    calls: list[tuple[Path, Path | None]] = []

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "package_release.py",
            "--output-dir",
            str(tmp_path / "dist"),
            "--python",
            "C:/Comfy/python.exe",
        ],
    )
    monkeypatch.setattr(package_release, "create_release_zip", lambda output_dir, archive_name: archive_path)

    def verify_stub(path: Path, python_executable: Path | None = None) -> tuple[bool, str]:
        calls.append((path, python_executable))
        return True, "runtime verified"

    monkeypatch.setattr(package_release, "verify_release_archive", verify_stub)

    exit_code = package_release.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert calls == [(archive_path, Path("C:/Comfy/python.exe"))]
    assert "runtime verified" in output


def test_main_surfaces_missing_runtime_python_error(monkeypatch, capsys, tmp_path: Path) -> None:
    archive_path = tmp_path / "dist" / "nanaix_Comfy.zip"
    missing_python = tmp_path / "missing-python.exe"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "package_release.py",
            "--output-dir",
            str(tmp_path / "dist"),
            "--python",
            str(missing_python),
        ],
    )
    monkeypatch.setattr(package_release, "create_release_zip", lambda output_dir, archive_name: archive_path)
    monkeypatch.setattr(
        package_release,
        "verify_release_archive",
        lambda path, python_executable=None: (False, f"Python executable does not exist: {python_executable}"),
    )

    exit_code = package_release.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Python executable does not exist" in output
    assert str(missing_python.resolve()) in output
