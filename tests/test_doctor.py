from __future__ import annotations

import sys
from utils.errors import NanaixNodeError
from pathlib import Path

from scripts import doctor


def test_collect_dependency_status_returns_known_keys() -> None:
    status = doctor.collect_dependency_status()

    assert "numpy" in status
    assert "PIL" in status
    assert "torch" in status


def test_build_report_includes_plugin_metadata(monkeypatch) -> None:
    monkeypatch.setattr(doctor, "collect_dependency_status", lambda: {"numpy": True, "PIL": True, "torch": False})
    monkeypatch.setattr(doctor, "find_custom_nodes_candidates", lambda roots, limit=5: [])

    report = doctor.build_report(limit=2, roots=[])

    assert "Plugin: nanaix_Comfy" in report
    assert "Version: 0.1.0" in report
    assert "torch: MISSING" in report


def test_build_report_pairs_custom_nodes_candidates_with_python(monkeypatch, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    python_executable = tmp_path / "ComfyUI" / "python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")

    monkeypatch.setattr(doctor, "collect_dependency_status", lambda: {"numpy": True, "PIL": True, "torch": True})
    monkeypatch.setattr(doctor, "find_custom_nodes_candidates", lambda roots, limit=5: [custom_nodes.resolve()])
    monkeypatch.setattr(
        doctor,
        "find_matching_python_for_custom_nodes",
        lambda path, limit=20: python_executable.resolve(),
        raising=False,
    )

    report = doctor.build_report(limit=2, roots=[tmp_path])

    assert f"custom_nodes={custom_nodes.resolve()}" in report
    assert f"python={python_executable.resolve()}" in report


def test_build_report_auto_verifies_best_discovered_candidate(monkeypatch, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    python_executable = tmp_path / "ComfyUI" / "python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")

    monkeypatch.setattr(doctor, "collect_dependency_status", lambda: {"numpy": True, "PIL": True, "torch": True})
    monkeypatch.setattr(doctor, "find_custom_nodes_candidates", lambda roots, limit=5: [custom_nodes.resolve()])
    monkeypatch.setattr(
        doctor,
        "find_matching_python_for_custom_nodes",
        lambda path, limit=20: python_executable.resolve(),
        raising=False,
    )
    monkeypatch.setattr(doctor, "verify_install", lambda path: (True, "Verified nanaix_Comfy v0.1.0"))
    monkeypatch.setattr(
        doctor,
        "verify_install_runtime",
        lambda custom_nodes_path, python_executable: (True, "Runtime verified auto candidate"),
        raising=False,
    )

    report = doctor.build_report(limit=2, roots=[tmp_path])

    assert "Auto verification:" in report
    assert "OK: Verified nanaix_Comfy v0.1.0" in report
    assert "Auto runtime verification:" in report
    assert "OK: Runtime verified auto candidate" in report


def test_build_report_includes_direct_verification(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(doctor, "collect_dependency_status", lambda: {"numpy": True, "PIL": True, "torch": True})
    monkeypatch.setattr(doctor, "find_custom_nodes_candidates", lambda roots, limit=5: [])
    monkeypatch.setattr(doctor, "verify_install", lambda path: (True, "Verified nanaix_Comfy v0.1.0"))

    report = doctor.build_report(custom_nodes=str(tmp_path / "custom_nodes"), limit=2, roots=[])

    assert "Direct verification:" in report
    assert "OK: Verified nanaix_Comfy v0.1.0" in report


def test_build_report_skips_global_candidate_scan_when_custom_nodes_is_explicit(monkeypatch, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    custom_nodes.mkdir(parents=True)

    monkeypatch.setattr(doctor, "collect_dependency_status", lambda: {"numpy": True, "PIL": True, "torch": True})
    monkeypatch.setattr(
        doctor,
        "find_custom_nodes_candidates",
        lambda roots, limit=5: (_ for _ in ()).throw(AssertionError("candidate scan should be skipped")),
    )
    monkeypatch.setattr(doctor, "verify_install", lambda path: (True, "Verified nanaix_Comfy v0.1.0"))

    report = doctor.build_report(custom_nodes=str(custom_nodes), limit=2, roots=[tmp_path])

    assert "Discovered custom_nodes candidates:" in report
    assert "- skipped because --custom-nodes was provided" in report


def test_build_report_includes_runtime_verification_when_python_is_matched(monkeypatch, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    python_executable = tmp_path / "ComfyUI" / "python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")

    monkeypatch.setattr(doctor, "collect_dependency_status", lambda: {"numpy": True, "PIL": True, "torch": True})
    monkeypatch.setattr(doctor, "find_custom_nodes_candidates", lambda roots, limit=5: [])
    monkeypatch.setattr(doctor, "verify_install", lambda path: (True, "Verified nanaix_Comfy v0.1.0"))
    monkeypatch.setattr(
        doctor,
        "find_matching_python_for_custom_nodes",
        lambda path, limit=20: python_executable.resolve(),
        raising=False,
    )
    monkeypatch.setattr(
        doctor,
        "verify_install_runtime",
        lambda custom_nodes_path, python_executable: (True, "Runtime verified nanaix_Comfy"),
        raising=False,
    )

    report = doctor.build_report(custom_nodes=str(custom_nodes), limit=2, roots=[tmp_path])

    assert "Runtime verification:" in report
    assert "OK: Runtime verified nanaix_Comfy" in report


def test_build_report_prefers_explicit_python_for_runtime_verification(monkeypatch, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    explicit_python = tmp_path / "custom-python" / "python.exe"
    matched_python = tmp_path / "matched-python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    explicit_python.parent.mkdir(parents=True)
    matched_python.parent.mkdir(parents=True)
    explicit_python.write_text("", encoding="utf-8")
    matched_python.write_text("", encoding="utf-8")
    calls: list[tuple[Path, Path]] = []

    monkeypatch.setattr(doctor, "collect_dependency_status", lambda: {"numpy": True, "PIL": True, "torch": True})
    monkeypatch.setattr(doctor, "find_custom_nodes_candidates", lambda roots, limit=5: [])
    monkeypatch.setattr(doctor, "verify_install", lambda path: (True, "Verified nanaix_Comfy v0.1.0"))
    monkeypatch.setattr(
        doctor,
        "find_matching_python_for_custom_nodes",
        lambda path, limit=20: matched_python.resolve(),
        raising=False,
    )

    def runtime_stub(custom_nodes_path: Path, python_executable: Path) -> tuple[bool, str]:
        calls.append((custom_nodes_path, python_executable))
        return True, "Runtime verified with explicit python"

    monkeypatch.setattr(doctor, "verify_install_runtime", runtime_stub, raising=False)

    report = doctor.build_report(
        custom_nodes=str(custom_nodes),
        python=str(explicit_python),
        limit=2,
        roots=[tmp_path],
    )

    assert calls == [(custom_nodes.resolve(), explicit_python.resolve())]
    assert "OK: Runtime verified with explicit python" in report


def test_main_prints_runtime_verification_when_custom_nodes_and_python_are_provided(monkeypatch, capsys, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    python_executable = tmp_path / "ComfyUI" / "python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "doctor.py",
            "--custom-nodes",
            str(custom_nodes),
            "--python",
            str(python_executable),
        ],
    )
    monkeypatch.setattr(doctor, "collect_dependency_status", lambda: {"numpy": True, "PIL": True, "torch": True})
    monkeypatch.setattr(doctor, "find_custom_nodes_candidates", lambda roots, limit=5: [])
    monkeypatch.setattr(doctor, "verify_install", lambda path: (True, "Verified nanaix_Comfy v0.1.0"))
    monkeypatch.setattr(doctor, "verify_install_runtime", lambda custom_nodes_path, python_executable: (True, "Runtime verified from CLI"))
    monkeypatch.delenv(doctor.IMAGE2_KEY_ENV, raising=False)
    monkeypatch.delenv(doctor.BANANA_KEY_ENV, raising=False)

    exit_code = doctor.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Runtime verification:" in output
    assert "OK: Runtime verified from CLI" in output


def test_main_prints_runtime_verification_when_python_is_auto_matched(monkeypatch, capsys, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    python_executable = tmp_path / "ComfyUI" / "python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "doctor.py",
            "--custom-nodes",
            str(custom_nodes),
        ],
    )
    monkeypatch.setattr(doctor, "collect_dependency_status", lambda: {"numpy": True, "PIL": True, "torch": True})
    monkeypatch.setattr(doctor, "find_custom_nodes_candidates", lambda roots, limit=5: [])
    monkeypatch.setattr(doctor, "verify_install", lambda path: (True, "Verified nanaix_Comfy v0.1.0"))
    monkeypatch.setattr(
        doctor,
        "find_matching_python_for_custom_nodes",
        lambda path, limit=20: python_executable.resolve(),
        raising=False,
    )
    monkeypatch.setattr(doctor, "verify_install_runtime", lambda custom_nodes_path, python_executable: (True, "Runtime verified from matched python"))
    monkeypatch.delenv(doctor.IMAGE2_KEY_ENV, raising=False)
    monkeypatch.delenv(doctor.BANANA_KEY_ENV, raising=False)

    exit_code = doctor.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Runtime verification:" in output
    assert "OK: Runtime verified from matched python" in output


def test_build_report_includes_hint_on_failed_direct_verification(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(doctor, "collect_dependency_status", lambda: {"numpy": True, "PIL": True, "torch": True})
    monkeypatch.setattr(doctor, "find_custom_nodes_candidates", lambda roots, limit=5: [])
    monkeypatch.setattr(doctor, "verify_install", lambda path: (False, "Failed to import nanaix_Comfy: No module named 'nanaix_Comfy'"))

    report = doctor.build_report(custom_nodes=str(tmp_path / "custom_nodes"), limit=2, roots=[])

    assert "Hint: run deploy_to_comfyui.py first" in report


def test_build_report_skips_provider_self_check_without_keys(monkeypatch) -> None:
    monkeypatch.setattr(doctor, "collect_dependency_status", lambda: {"numpy": True, "PIL": True, "torch": True})
    monkeypatch.setattr(doctor, "find_custom_nodes_candidates", lambda roots, limit=5: [])
    monkeypatch.delenv(doctor.IMAGE2_KEY_ENV, raising=False)
    monkeypatch.delenv(doctor.BANANA_KEY_ENV, raising=False)

    report = doctor.build_report(limit=2, roots=[])

    assert "Provider self-check:" in report
    assert f"image-2: skipped (set {doctor.IMAGE2_KEY_ENV} to verify /models visibility)" in report
    assert f"nano-banana: skipped (set {doctor.BANANA_KEY_ENV} to verify configured model visibility)" in report


def test_build_report_includes_provider_visible_models(monkeypatch) -> None:
    monkeypatch.setattr(doctor, "collect_dependency_status", lambda: {"numpy": True, "PIL": True, "torch": True})
    monkeypatch.setattr(doctor, "find_custom_nodes_candidates", lambda roots, limit=5: [])
    monkeypatch.setattr(
        doctor,
        "collect_provider_model_visibility",
        lambda image2_api_key="", banana_api_key="": [
            "image-2: OK - visible models: gpt-image-2, gpt-image-2-mini",
            "nano-banana: OK - visible models: nano-banana-2, nano-banana-pro",
        ],
    )

    report = doctor.build_report(limit=2, roots=[])

    assert "Provider self-check:" in report
    assert "image-2: OK - visible models: gpt-image-2, gpt-image-2-mini" in report
    assert "nano-banana: OK - visible models: nano-banana-2, nano-banana-pro" in report


def test_collect_provider_model_visibility_reports_missing_image2_model(monkeypatch) -> None:
    class StubImage2Client:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def list_models(self, *, node_name: str) -> list[str]:
            return ["other-model"]

    monkeypatch.setattr(doctor, "Image2Client", StubImage2Client)

    lines = doctor.collect_provider_model_visibility(image2_api_key="image2-key")

    assert "image-2: FAIL - gpt-image-2 is not visible for this key (visible: other-model)" in lines
    assert any("check whether this key belongs to the Nanaix image group" in line for line in lines)
    assert f"nano-banana: skipped (set {doctor.BANANA_KEY_ENV} to verify configured model visibility)" in lines


def test_collect_provider_model_visibility_reports_client_errors(monkeypatch) -> None:
    class StubImage2Client:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def list_models(self, *, node_name: str) -> list[str]:
            raise NanaixNodeError("Doctor: gpt-image-2 failed during model list request (HTTP 401): Invalid API key")

    monkeypatch.setattr(doctor, "Image2Client", StubImage2Client)

    lines = doctor.collect_provider_model_visibility(image2_api_key="image2-key")

    assert "image-2: FAIL - Doctor: gpt-image-2 failed during model list request (HTTP 401): Invalid API key" in lines
    assert f"nano-banana: skipped (set {doctor.BANANA_KEY_ENV} to verify configured model visibility)" in lines


def test_collect_provider_model_visibility_reports_missing_banana_model(monkeypatch) -> None:
    class StubBananaClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def list_models(self, *, node_name: str) -> list[str]:
            return ["nano-banana-2"]

    monkeypatch.setattr(doctor, "BananaClient", StubBananaClient)

    lines = doctor.collect_provider_model_visibility(banana_api_key="banana-key")

    assert f"image-2: skipped (set {doctor.IMAGE2_KEY_ENV} to verify /models visibility)" in lines
    assert "nano-banana: FAIL - missing expected models: nano-banana-pro (visible: nano-banana-2)" in lines
    assert any("confirm that this key is attached to a nano-banana-enabled account group" in line for line in lines)
