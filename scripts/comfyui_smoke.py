from __future__ import annotations

import argparse
import http.client
import json
import tempfile
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib import request
from urllib.error import HTTPError, URLError


EXPECTED_NODES = ["Nanaix_Text", "Nanaix_Image"]


@dataclass
class SmokeReport:
    ok: bool
    lines: list[str]

    def render(self) -> str:
        return "\n".join(self.lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch ComfyUI and verify Nanaix nodes are registered through /object_info.")
    parser.add_argument("--comfy-root", required=True, help="Path to the ComfyUI root directory containing main.py")
    parser.add_argument("--python", required=True, help="Path to the ComfyUI Python executable")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind ComfyUI to for the smoke check")
    parser.add_argument("--port", type=int, default=8191, help="Port to bind ComfyUI to for the smoke check")
    parser.add_argument("--timeout", type=float, default=60.0, help="Maximum seconds to wait for node registration")
    return parser.parse_args()


def build_object_info_url(host: str, port: int, node_name: str) -> str:
    return f"http://{host}:{port}/object_info/{node_name}"


def fetch_json(url: str):
    with request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def probe_server_ready(host: str, port: int) -> bool:
    try:
        with request.urlopen(f"http://{host}:{port}/object_info", timeout=2) as response:
            body = response.read().decode("utf-8", errors="replace").strip()
    except (URLError, HTTPError, http.client.RemoteDisconnected, json.JSONDecodeError, TimeoutError):
        return False
    return bool(body)


def verify_registered_nodes(
    *,
    host: str,
    port: int,
    expected_nodes: list[str],
    fetch_json: Callable[[str], dict] = fetch_json,
) -> tuple[bool, str]:
    found: list[str] = []
    for node_name in expected_nodes:
        try:
            payload = fetch_json(build_object_info_url(host, port, node_name))
        except (URLError, HTTPError, http.client.RemoteDisconnected, json.JSONDecodeError) as error:
            return False, f"ComfyUI not ready yet: {error}"
        if node_name not in payload:
            return False, f"Missing node in /object_info: {node_name}"
        found.append(node_name)
    return True, f"Registered nodes: {', '.join(found)}"


def launch_comfyui_process(command: list[str], cwd: Path):
    stdout_handle = tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", suffix=".log", prefix="nanaix-comfyui-stdout-", delete=False)
    stderr_handle = tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", suffix=".log", prefix="nanaix-comfyui-stderr-", delete=False)
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=stdout_handle,
        stderr=stderr_handle,
        text=True,
    )
    process.stdout_log_path = Path(stdout_handle.name)
    process.stderr_log_path = Path(stderr_handle.name)
    process._stdout_log_handle = stdout_handle
    process._stderr_log_handle = stderr_handle
    return process


def collect_process_output(process) -> list[str]:
    stdout_log_path = getattr(process, "stdout_log_path", None)
    stderr_log_path = getattr(process, "stderr_log_path", None)
    if stdout_log_path or stderr_log_path:
        lines: list[str] = []
        if stdout_log_path and Path(stdout_log_path).exists():
            stdout = Path(stdout_log_path).read_text(encoding="utf-8", errors="replace")
            if stdout:
                lines.append("ComfyUI stdout:")
                lines.extend(line for line in stdout.strip().splitlines() if line.strip())
        if stderr_log_path and Path(stderr_log_path).exists():
            stderr = Path(stderr_log_path).read_text(encoding="utf-8", errors="replace")
            if stderr:
                lines.append("ComfyUI stderr:")
                lines.extend(line for line in stderr.strip().splitlines() if line.strip())
        return lines

    if not hasattr(process, "communicate"):
        return []
    try:
        stdout, stderr = process.communicate(timeout=1)
    except Exception:
        return []

    lines: list[str] = []
    if stdout:
        lines.append("ComfyUI stdout:")
        lines.extend(line for line in stdout.strip().splitlines() if line.strip())
    if stderr:
        lines.append("ComfyUI stderr:")
        lines.extend(line for line in stderr.strip().splitlines() if line.strip())
    return lines


def stop_process(process) -> None:
    if process.poll() is not None:
        close_process_logs(process)
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
    finally:
        close_process_logs(process)


def close_process_logs(process) -> None:
    for handle_name in ("_stdout_log_handle", "_stderr_log_handle"):
        handle = getattr(process, handle_name, None)
        if handle is None:
            continue
        try:
            handle.flush()
        except Exception:
            pass
        try:
            handle.close()
        except Exception:
            pass


def run_smoke_check(
    *,
    comfy_root: Path,
    python_executable: Path,
    host: str,
    port: int,
    timeout: float = 60.0,
    launch_process: Callable[[list[str], Path], object] = launch_comfyui_process,
    verify_nodes: Callable[..., tuple[bool, str]] = verify_registered_nodes,
    readiness_probe: Callable[[str, int], bool] = probe_server_ready,
) -> SmokeReport:
    main_script = comfy_root / "main.py"
    command = [
        str(python_executable),
        str(main_script),
        "--listen",
        host,
        "--port",
        str(port),
        "--disable-auto-launch",
        "--dont-print-server",
        "--disable-all-custom-nodes",
        "--whitelist-custom-nodes",
        "nanaix_Comfy",
    ]
    lines = [f"Launching ComfyUI: {' '.join(command)}"]
    process = launch_process(command, comfy_root)
    started_at = time.time()

    try:
        while time.time() - started_at <= timeout:
            if process.poll() not in (None,):
                exit_lines = [f"ComfyUI exited early with code {process.poll()}"]
                exit_lines.extend(collect_process_output(process))
                return SmokeReport(False, lines + exit_lines)

            if not readiness_probe(host, port):
                time.sleep(1.0)
                continue

            ok, message = verify_nodes(host=host, port=port, expected_nodes=EXPECTED_NODES)
            if ok:
                lines.append(message)
                return SmokeReport(True, lines)
            lowered_message = message.lower()
            if "missing" in lowered_message and "nanaix_" in lowered_message:
                lines.append(message)
                return SmokeReport(False, lines)
            time.sleep(1.0)
        stop_process(process)
        timeout_lines = [f"Timed out after {timeout:.1f}s waiting for Nanaix nodes to register"]
        timeout_lines.extend(collect_process_output(process))
        return SmokeReport(False, lines + timeout_lines)
    finally:
        if process.poll() is None:
            stop_process(process)


def main() -> int:
    args = parse_args()
    report = run_smoke_check(
        comfy_root=Path(args.comfy_root).resolve(),
        python_executable=Path(args.python).resolve(),
        host=args.host,
        port=args.port,
        timeout=args.timeout,
    )
    print(report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
