from __future__ import annotations

import http.client
import json
from pathlib import Path
from urllib.error import URLError

from scripts import comfyui_smoke


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.killed = False
        self.returncode = None
        self._stdout = ""
        self._stderr = ""

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode

    def communicate(self, timeout=None):
        return (self._stdout, self._stderr)


def test_build_object_info_url_targets_node_endpoint() -> None:
    url = comfyui_smoke.build_object_info_url("127.0.0.1", 8191, "Nanaix_Text")

    assert url == "http://127.0.0.1:8191/object_info/Nanaix_Text"


def test_verify_registered_nodes_succeeds_when_all_nodes_appear() -> None:
    requested = []

    def fetch_json(url: str):
        requested.append(url)
        if url.endswith("/Nanaix_Text"):
            return {"Nanaix_Text": {"input": {}}}
        if url.endswith("/Nanaix_Image"):
            return {"Nanaix_Image": {"input": {}}}
        raise AssertionError(f"Unexpected URL: {url}")

    ok, message = comfyui_smoke.verify_registered_nodes(
        host="127.0.0.1",
        port=8191,
        expected_nodes=["Nanaix_Text", "Nanaix_Image"],
        fetch_json=fetch_json,
    )

    assert ok
    assert "Nanaix_Text" in message
    assert "Nanaix_Image" in message
    assert len(requested) == 2


def test_verify_registered_nodes_returns_retryable_message_on_connection_error() -> None:
    def fetch_json(url: str):
        raise URLError("connection refused")

    ok, message = comfyui_smoke.verify_registered_nodes(
        host="127.0.0.1",
        port=8191,
        expected_nodes=["Nanaix_Text"],
        fetch_json=fetch_json,
    )

    assert not ok
    assert "not ready yet" in message


def test_verify_registered_nodes_returns_retryable_message_on_remote_disconnect() -> None:
    def fetch_json(url: str):
        raise http.client.RemoteDisconnected("Remote end closed connection without response")

    ok, message = comfyui_smoke.verify_registered_nodes(
        host="127.0.0.1",
        port=8191,
        expected_nodes=["Nanaix_Text"],
        fetch_json=fetch_json,
    )

    assert not ok
    assert "not ready yet" in message


def test_verify_registered_nodes_returns_retryable_message_on_invalid_json() -> None:
    def fetch_json(url: str):
        raise json.JSONDecodeError("Expecting value", "", 0)

    ok, message = comfyui_smoke.verify_registered_nodes(
        host="127.0.0.1",
        port=8191,
        expected_nodes=["Nanaix_Text"],
        fetch_json=fetch_json,
    )

    assert not ok
    assert "not ready yet" in message


def test_run_smoke_check_terminates_process_after_success(tmp_path: Path) -> None:
    comfy_root = tmp_path / "ComfyUI"
    python_executable = tmp_path / "python.exe"
    main_script = comfy_root / "main.py"
    comfy_root.mkdir()
    python_executable.write_text("", encoding="utf-8")
    main_script.write_text("", encoding="utf-8")
    process = FakeProcess()

    report = comfyui_smoke.run_smoke_check(
        comfy_root=comfy_root,
        python_executable=python_executable,
        host="127.0.0.1",
        port=8191,
        launch_process=lambda command, cwd: process,
        verify_nodes=lambda host, port, expected_nodes, fetch_json=None: (True, "registered"),
        readiness_probe=lambda host, port: True,
    )

    assert report.ok
    assert process.terminated
    assert "--disable-all-custom-nodes" in report.lines[0]
    assert "--whitelist-custom-nodes nanaix_Comfy" in report.lines[0]
    assert any("registered" in line for line in report.lines)


def test_run_smoke_check_waits_for_readiness_probe_before_registration_checks(tmp_path: Path) -> None:
    comfy_root = tmp_path / "ComfyUI"
    python_executable = tmp_path / "python.exe"
    main_script = comfy_root / "main.py"
    comfy_root.mkdir()
    python_executable.write_text("", encoding="utf-8")
    main_script.write_text("", encoding="utf-8")
    process = FakeProcess()
    readiness_checks = {"count": 0}
    verify_calls = {"count": 0}

    def probe(host: str, port: int) -> bool:
        readiness_checks["count"] += 1
        return readiness_checks["count"] >= 3

    def verify_nodes(host, port, expected_nodes, fetch_json=None):
        verify_calls["count"] += 1
        return (True, "registered")

    report = comfyui_smoke.run_smoke_check(
        comfy_root=comfy_root,
        python_executable=python_executable,
        host="127.0.0.1",
        port=8191,
        launch_process=lambda command, cwd: process,
        verify_nodes=verify_nodes,
        readiness_probe=probe,
    )

    assert report.ok
    assert readiness_checks["count"] == 3
    assert verify_calls["count"] == 1


def test_run_smoke_check_reports_registration_failure(tmp_path: Path) -> None:
    comfy_root = tmp_path / "ComfyUI"
    python_executable = tmp_path / "python.exe"
    main_script = comfy_root / "main.py"
    comfy_root.mkdir()
    python_executable.write_text("", encoding="utf-8")
    main_script.write_text("", encoding="utf-8")
    process = FakeProcess()

    report = comfyui_smoke.run_smoke_check(
        comfy_root=comfy_root,
        python_executable=python_executable,
        host="127.0.0.1",
        port=8191,
        launch_process=lambda command, cwd: process,
        verify_nodes=lambda host, port, expected_nodes, fetch_json=None: (False, "missing Nanaix_Text"),
        readiness_probe=lambda host, port: True,
    )

    assert not report.ok
    assert process.terminated
    assert any("missing Nanaix_Text" in line for line in report.lines)


def test_run_smoke_check_includes_process_output_when_comfyui_exits_early(tmp_path: Path) -> None:
    comfy_root = tmp_path / "ComfyUI"
    python_executable = tmp_path / "python.exe"
    main_script = comfy_root / "main.py"
    comfy_root.mkdir()
    python_executable.write_text("", encoding="utf-8")
    main_script.write_text("", encoding="utf-8")
    process = FakeProcess()
    process.returncode = 1
    process._stderr = "startup failed"

    report = comfyui_smoke.run_smoke_check(
        comfy_root=comfy_root,
        python_executable=python_executable,
        host="127.0.0.1",
        port=8191,
        launch_process=lambda command, cwd: process,
        verify_nodes=lambda host, port, expected_nodes, fetch_json=None: (False, "not ready yet"),
        readiness_probe=lambda host, port: True,
    )

    assert not report.ok
    assert any("startup failed" in line for line in report.lines)


def test_run_smoke_check_includes_process_output_after_timeout(tmp_path: Path) -> None:
    comfy_root = tmp_path / "ComfyUI"
    python_executable = tmp_path / "python.exe"
    main_script = comfy_root / "main.py"
    comfy_root.mkdir()
    python_executable.write_text("", encoding="utf-8")
    main_script.write_text("", encoding="utf-8")
    process = FakeProcess()
    process._stderr = "still starting"

    report = comfyui_smoke.run_smoke_check(
        comfy_root=comfy_root,
        python_executable=python_executable,
        host="127.0.0.1",
        port=8191,
        timeout=0.01,
        launch_process=lambda command, cwd: process,
        verify_nodes=lambda host, port, expected_nodes, fetch_json=None: (False, "not ready yet"),
        readiness_probe=lambda host, port: False,
    )

    assert not report.ok
    assert process.terminated
    assert any("still starting" in line for line in report.lines)


def test_collect_process_output_reads_from_log_files_when_present(tmp_path: Path) -> None:
    stdout_path = tmp_path / "stdout.log"
    stderr_path = tmp_path / "stderr.log"
    stdout_path.write_text("line one\nline two\n", encoding="utf-8")
    stderr_path.write_text("err one\n", encoding="utf-8")

    process = type(
        "LoggedProcess",
        (),
        {
            "stdout_log_path": stdout_path,
            "stderr_log_path": stderr_path,
        },
    )()

    lines = comfyui_smoke.collect_process_output(process)

    assert lines == [
        "ComfyUI stdout:",
        "line one",
        "line two",
        "ComfyUI stderr:",
        "err one",
    ]
