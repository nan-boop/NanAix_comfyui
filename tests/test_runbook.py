from __future__ import annotations

from pathlib import Path

from scripts import runbook


def test_runbook_execute_chains_detection_deploy_and_both_verifications(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    custom_nodes_path = custom_nodes.resolve()
    comfy_root = custom_nodes.parent.resolve()
    python_executable = tmp_path / "python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")
    workflow_calls = []
    live_calls = []

    def workflow_smoke_stub(workflow_paths, comfy_root, python_executable, host, port, timeout, verify_saved_images=False):
        workflow_calls.append(
            {
                "host": host,
                "port": port,
                "workflow_paths": workflow_paths,
                "comfy_root": comfy_root,
                "python_executable": python_executable,
                "timeout": timeout,
                "verify_saved_images": verify_saved_images,
            }
        )
        return [
            runbook.RunbookReport(True, ["Queued minimal_text_workflow.json", "Node errors: {}"]),
            runbook.RunbookReport(True, ["Queued minimal_image_workflow.json", "Node errors: {}"]),
        ]

    def live_smoke_stub(comfy_root, python_executable, host, port):
        live_calls.append((comfy_root, python_executable, host, port))
        return None

    report = runbook.execute(
        custom_nodes="",
        comfy_python=str(python_executable),
        roots=[tmp_path],
        force=True,
        smoke_host="127.0.0.1",
        smoke_port=8191,
        smoke_timeout=45.0,
        run_smoke=True,
        resolve_custom_nodes_path=lambda custom_nodes, roots=None: custom_nodes and Path(custom_nodes).resolve() or custom_nodes_path,
        find_best_python=lambda roots=None: python_executable.resolve(),
        deploy_fn=lambda path, force=False: (True, "deployed"),
        verify_fn=lambda path: (True, "light ok"),
        verify_runtime_fn=lambda path, python_executable: (True, "runtime ok"),
        smoke_check_fn=lambda comfy_root, python_executable, host, port, timeout: runbook.RunbookReport(True, ["Registered nodes: Nanaix_Text, Nanaix_Image"]),
        multi_workflow_smoke_fn=workflow_smoke_stub,
        doctor_self_check_fn=lambda: ["image-2: skipped", "nano-banana: skipped"],
        detect_live_keys_fn=lambda: False,
        live_smoke_fn=live_smoke_stub,
    )

    assert report.ok
    assert report.custom_nodes_path == custom_nodes_path
    assert report.python_executable == python_executable.resolve()
    assert any("Auto-detected custom_nodes" in line for line in report.lines)
    assert any("Deployment: deployed" in line for line in report.lines)
    assert any("Direct verification: light ok" in line for line in report.lines)
    assert any("Runtime verification: runtime ok" in line for line in report.lines)
    assert any("Doctor self-check: image-2: skipped" in line for line in report.lines)
    assert any("Doctor self-check: nano-banana: skipped" in line for line in report.lines)
    assert any("Registration smoke check: Registered nodes: Nanaix_Text, Nanaix_Image" in line for line in report.lines)
    assert any("Text workflow smoke check: Queued minimal_text_workflow.json" in line for line in report.lines)
    assert any("Image workflow smoke check: Queued minimal_image_workflow.json" in line for line in report.lines)
    assert any("Live ComfyUI smoke: skipped because no Nanaix API key is configured." in line for line in report.lines)
    assert [[path.name for path in call["workflow_paths"]] for call in workflow_calls] == [[
        "minimal_text_workflow.json",
        "minimal_image_workflow.json",
    ]]
    assert live_calls == []


def test_runbook_execute_stops_after_failed_deploy(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    custom_nodes.mkdir(parents=True)

    report = runbook.execute(
        custom_nodes=str(custom_nodes),
        comfy_python="",
        roots=[tmp_path],
        force=True,
        smoke_host="127.0.0.1",
        smoke_port=8191,
        smoke_timeout=45.0,
        run_smoke=True,
        resolve_custom_nodes_path=lambda custom_nodes, roots=None: Path(custom_nodes).resolve(),
        find_best_python=lambda roots=None: None,
        deploy_fn=lambda path, force=False: (False, "deploy failed"),
        verify_fn=lambda path: (_ for _ in ()).throw(AssertionError("verify_fn should not be called")),
        verify_runtime_fn=lambda path, python_executable: (_ for _ in ()).throw(AssertionError("verify_runtime_fn should not be called")),
        smoke_check_fn=lambda comfy_root, python_executable, host, port, timeout: (_ for _ in ()).throw(AssertionError("smoke_check_fn should not be called")),
        multi_workflow_smoke_fn=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("multi_workflow_smoke_fn should not be called")),
        doctor_self_check_fn=lambda: ["image-2: skipped", "nano-banana: skipped"],
        detect_live_keys_fn=lambda: (_ for _ in ()).throw(AssertionError("detect_live_keys_fn should not be called")),
        live_smoke_fn=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("live_smoke_fn should not be called")),
    )

    assert not report.ok
    assert any("Deployment: deploy failed" in line for line in report.lines)
    assert any("Doctor self-check: image-2: skipped" in line for line in report.lines)
    assert not any("Direct verification" in line for line in report.lines)


def test_runbook_execute_continues_when_doctor_self_check_raises(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    python_executable = tmp_path / "python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")

    report = runbook.execute(
        custom_nodes=str(custom_nodes),
        comfy_python=str(python_executable),
        roots=[tmp_path],
        force=True,
        smoke_host="127.0.0.1",
        smoke_port=8191,
        smoke_timeout=45.0,
        run_smoke=False,
        resolve_custom_nodes_path=lambda custom_nodes, roots=None: Path(custom_nodes).resolve(),
        find_best_python=lambda roots=None: python_executable.resolve(),
        deploy_fn=lambda path, force=False: (True, "deployed"),
        verify_fn=lambda path: (True, "light ok"),
        verify_runtime_fn=lambda path, python_executable: (True, "runtime ok"),
        smoke_check_fn=lambda comfy_root, python_executable, host, port, timeout: (_ for _ in ()).throw(AssertionError("smoke_check_fn should not be called")),
        multi_workflow_smoke_fn=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("multi_workflow_smoke_fn should not be called")),
        doctor_self_check_fn=lambda: (_ for _ in ()).throw(RuntimeError("network down")),
        detect_live_keys_fn=lambda: (_ for _ in ()).throw(AssertionError("detect_live_keys_fn should not be called")),
        live_smoke_fn=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("live_smoke_fn should not be called")),
    )

    assert report.ok
    assert any("Doctor self-check: unavailable: network down" in line for line in report.lines)
    assert any("Deployment: deployed" in line for line in report.lines)


def test_runbook_execute_fails_when_registration_smoke_check_fails(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    python_executable = tmp_path / "python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")

    report = runbook.execute(
        custom_nodes=str(custom_nodes),
        comfy_python=str(python_executable),
        roots=[tmp_path],
        force=True,
        smoke_host="127.0.0.1",
        smoke_port=8191,
        smoke_timeout=45.0,
        run_smoke=True,
        resolve_custom_nodes_path=lambda custom_nodes, roots=None: Path(custom_nodes).resolve(),
        find_best_python=lambda roots=None: python_executable.resolve(),
        deploy_fn=lambda path, force=False: (True, "deployed"),
        verify_fn=lambda path: (True, "light ok"),
        verify_runtime_fn=lambda path, python_executable: (True, "runtime ok"),
        smoke_check_fn=lambda comfy_root, python_executable, host, port, timeout: runbook.RunbookReport(False, ["Timed out after 45.0s waiting for Nanaix nodes to register"]),
        multi_workflow_smoke_fn=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("multi_workflow_smoke_fn should not be called")),
        detect_live_keys_fn=lambda: False,
        live_smoke_fn=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("live_smoke_fn should not be called")),
    )

    assert not report.ok
    assert any("Registration smoke check: Timed out after 45.0s waiting for Nanaix nodes to register" in line for line in report.lines)


def test_runbook_execute_passes_custom_smoke_options(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    python_executable = tmp_path / "python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")
    recorded = {}
    workflow_calls = []
    live_calls = []

    def smoke_stub(comfy_root, python_executable, host, port, timeout):
        recorded["comfy_root"] = comfy_root
        recorded["python_executable"] = python_executable
        recorded["host"] = host
        recorded["port"] = port
        recorded["timeout"] = timeout
        return runbook.RunbookReport(True, ["Registered nodes: Nanaix_Text, Nanaix_Image"])

    def workflow_smoke_stub(workflow_paths, comfy_root, python_executable, host, port, timeout, verify_saved_images=False):
        workflow_calls.append(
            {
                "host": host,
                "port": port,
                "workflow_paths": workflow_paths,
                "comfy_root": comfy_root,
                "python_executable": python_executable,
                "timeout": timeout,
                "verify_saved_images": verify_saved_images,
            }
        )
        return [
            runbook.RunbookReport(True, ["Queued minimal_text_workflow.json"]),
            runbook.RunbookReport(True, ["Queued minimal_image_workflow.json"]),
        ]

    def live_smoke_stub(comfy_root, python_executable, host, port):
        live_calls.append((comfy_root, python_executable, host, port))
        return runbook.RunbookReport(True, ["Text live smoke saved 1 image", "Image live smoke saved 1 image"])

    report = runbook.execute(
        custom_nodes=str(custom_nodes),
        comfy_python=str(python_executable),
        roots=[tmp_path],
        force=True,
        smoke_host="0.0.0.0",
        smoke_port=9001,
        smoke_timeout=12.5,
        run_smoke=True,
        resolve_custom_nodes_path=lambda custom_nodes, roots=None: Path(custom_nodes).resolve(),
        find_best_python=lambda roots=None: python_executable.resolve(),
        deploy_fn=lambda path, force=False: (True, "deployed"),
        verify_fn=lambda path: (True, "light ok"),
        verify_runtime_fn=lambda path, python_executable: (True, "runtime ok"),
        smoke_check_fn=smoke_stub,
        multi_workflow_smoke_fn=workflow_smoke_stub,
        detect_live_keys_fn=lambda: True,
        live_smoke_fn=live_smoke_stub,
    )

    assert report.ok
    assert recorded["host"] == "0.0.0.0"
    assert recorded["port"] == 9001
    assert recorded["timeout"] == 12.5
    assert len(workflow_calls) == 1
    assert workflow_calls[0]["host"] == "0.0.0.0"
    assert workflow_calls[0]["timeout"] == 12.5
    assert [path.name for path in workflow_calls[0]["workflow_paths"]] == [
        "minimal_text_workflow.json",
        "minimal_image_workflow.json",
    ]
    assert live_calls == [(custom_nodes.resolve().parent, python_executable.resolve(), "0.0.0.0", 9001)]
    assert any("Live ComfyUI smoke: Text live smoke saved 1 image" in line for line in report.lines)
    assert any("Live ComfyUI smoke: Image live smoke saved 1 image" in line for line in report.lines)


def test_runbook_execute_enables_saved_image_verification_for_workflow_smoke_when_keys_are_present(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    python_executable = tmp_path / "python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")
    workflow_calls = []

    def workflow_smoke_stub(workflow_paths, comfy_root, python_executable, host, port, timeout, verify_saved_images=False):
        workflow_calls.append(
            {
                "host": host,
                "port": port,
                "workflow_paths": workflow_paths,
                "comfy_root": comfy_root,
                "python_executable": python_executable,
                "timeout": timeout,
                "verify_saved_images": verify_saved_images,
            }
        )
        return [
            runbook.RunbookReport(True, ["Queued minimal_text_workflow.json", "Saved images: 1"]),
            runbook.RunbookReport(True, ["Queued minimal_image_workflow.json", "Saved images: 1"]),
        ]

    report = runbook.execute(
        custom_nodes=str(custom_nodes),
        comfy_python=str(python_executable),
        roots=[tmp_path],
        force=True,
        smoke_host="127.0.0.1",
        smoke_port=8191,
        smoke_timeout=45.0,
        run_smoke=True,
        resolve_custom_nodes_path=lambda custom_nodes, roots=None: Path(custom_nodes).resolve(),
        find_best_python=lambda roots=None: python_executable.resolve(),
        deploy_fn=lambda path, force=False: (True, "deployed"),
        verify_fn=lambda path: (True, "light ok"),
        verify_runtime_fn=lambda path, python_executable: (True, "runtime ok"),
        smoke_check_fn=lambda comfy_root, python_executable, host, port, timeout: runbook.RunbookReport(True, ["Registered nodes: Nanaix_Text, Nanaix_Image"]),
        multi_workflow_smoke_fn=workflow_smoke_stub,
        detect_live_keys_fn=lambda: True,
        live_smoke_fn=lambda comfy_root, python_executable, host, port: runbook.RunbookReport(True, ["mode=text saved=1", "mode=image saved=1"]),
    )

    assert report.ok
    assert len(workflow_calls) == 1
    assert workflow_calls[0]["verify_saved_images"] is True
    assert any("Text workflow smoke check: Saved images: 1" in line for line in report.lines)


def test_runbook_execute_can_skip_smoke_check(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    python_executable = tmp_path / "python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")

    report = runbook.execute(
        custom_nodes=str(custom_nodes),
        comfy_python=str(python_executable),
        roots=[tmp_path],
        force=True,
        smoke_host="127.0.0.1",
        smoke_port=8191,
        smoke_timeout=45.0,
        run_smoke=False,
        resolve_custom_nodes_path=lambda custom_nodes, roots=None: Path(custom_nodes).resolve(),
        find_best_python=lambda roots=None: python_executable.resolve(),
        deploy_fn=lambda path, force=False: (True, "deployed"),
        verify_fn=lambda path: (True, "light ok"),
        verify_runtime_fn=lambda path, python_executable: (True, "runtime ok"),
        smoke_check_fn=lambda comfy_root, python_executable, host, port, timeout: (_ for _ in ()).throw(AssertionError("smoke_check_fn should not be called")),
        multi_workflow_smoke_fn=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("multi_workflow_smoke_fn should not be called")),
        detect_live_keys_fn=lambda: (_ for _ in ()).throw(AssertionError("detect_live_keys_fn should not be called")),
        live_smoke_fn=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("live_smoke_fn should not be called")),
    )

    assert report.ok
    assert any("Registration smoke check: skipped by option." in line for line in report.lines)


def test_runbook_execute_fails_when_text_workflow_smoke_fails(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    python_executable = tmp_path / "python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")

    def workflow_smoke_stub(workflow_paths, comfy_root, python_executable, host, port, timeout, verify_saved_images=False):
        return [
            runbook.RunbookReport(False, ["ComfyUI /prompt returned HTTP 400"]),
            runbook.RunbookReport(True, ["Queued minimal_image_workflow.json"]),
        ]

    report = runbook.execute(
        custom_nodes=str(custom_nodes),
        comfy_python=str(python_executable),
        roots=[tmp_path],
        force=True,
        smoke_host="127.0.0.1",
        smoke_port=8191,
        smoke_timeout=45.0,
        run_smoke=True,
        resolve_custom_nodes_path=lambda custom_nodes, roots=None: Path(custom_nodes).resolve(),
        find_best_python=lambda roots=None: python_executable.resolve(),
        deploy_fn=lambda path, force=False: (True, "deployed"),
        verify_fn=lambda path: (True, "light ok"),
        verify_runtime_fn=lambda path, python_executable: (True, "runtime ok"),
        smoke_check_fn=lambda comfy_root, python_executable, host, port, timeout: runbook.RunbookReport(True, ["Registered nodes: Nanaix_Text, Nanaix_Image"]),
        multi_workflow_smoke_fn=workflow_smoke_stub,
        detect_live_keys_fn=lambda: False,
        live_smoke_fn=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("live_smoke_fn should not be called")),
    )

    assert not report.ok
    assert any("Text workflow smoke check: ComfyUI /prompt returned HTTP 400" in line for line in report.lines)
    assert not any("Image workflow smoke check:" in line for line in report.lines)


def test_runbook_execute_fails_when_live_smoke_fails(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    python_executable = tmp_path / "python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")

    report = runbook.execute(
        custom_nodes=str(custom_nodes),
        comfy_python=str(python_executable),
        roots=[tmp_path],
        force=True,
        smoke_host="127.0.0.1",
        smoke_port=8191,
        smoke_timeout=45.0,
        run_smoke=True,
        resolve_custom_nodes_path=lambda custom_nodes, roots=None: Path(custom_nodes).resolve(),
        find_best_python=lambda roots=None: python_executable.resolve(),
        deploy_fn=lambda path, force=False: (True, "deployed"),
        verify_fn=lambda path: (True, "light ok"),
        verify_runtime_fn=lambda path, python_executable: (True, "runtime ok"),
        smoke_check_fn=lambda comfy_root, python_executable, host, port, timeout: runbook.RunbookReport(True, ["Registered nodes: Nanaix_Text, Nanaix_Image"]),
        multi_workflow_smoke_fn=lambda *args, **kwargs: [
            runbook.RunbookReport(True, ["Queued minimal_text_workflow.json"]),
            runbook.RunbookReport(True, ["Queued minimal_image_workflow.json"]),
        ],
        detect_live_keys_fn=lambda: True,
        live_smoke_fn=lambda comfy_root, python_executable, host, port: runbook.RunbookReport(False, ["Prompt completed without saved output images"]),
    )

    assert not report.ok
    assert any("Live ComfyUI smoke: Prompt completed without saved output images" in line for line in report.lines)


def test_runbook_execute_wraps_live_smoke_exception_into_report(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    python_executable = tmp_path / "python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")

    report = runbook.execute(
        custom_nodes=str(custom_nodes),
        comfy_python=str(python_executable),
        roots=[tmp_path],
        force=True,
        smoke_host="127.0.0.1",
        smoke_port=8191,
        smoke_timeout=45.0,
        run_smoke=True,
        resolve_custom_nodes_path=lambda custom_nodes, roots=None: Path(custom_nodes).resolve(),
        find_best_python=lambda roots=None: python_executable.resolve(),
        deploy_fn=lambda path, force=False: (True, "deployed"),
        verify_fn=lambda path: (True, "light ok"),
        verify_runtime_fn=lambda path, python_executable: (True, "runtime ok"),
        smoke_check_fn=lambda comfy_root, python_executable, host, port, timeout: runbook.RunbookReport(True, ["Registered nodes: Nanaix_Text, Nanaix_Image"]),
        multi_workflow_smoke_fn=lambda *args, **kwargs: [
            runbook.RunbookReport(True, ["Queued minimal_text_workflow.json"]),
            runbook.RunbookReport(True, ["Queued minimal_image_workflow.json"]),
        ],
        detect_live_keys_fn=lambda: True,
        live_smoke_fn=lambda comfy_root, python_executable, host, port: (_ for _ in ()).throw(
            RuntimeError("ComfyUI /prompt failed with HTTP 400: missing prompt")
        ),
    )

    assert not report.ok
    assert any(
        "Live ComfyUI smoke: unavailable: ComfyUI /prompt failed with HTTP 400: missing prompt" in line
        for line in report.lines
    )


def test_runbook_default_live_smoke_runs_both_text_and_image_paths(tmp_path: Path, monkeypatch) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    python_executable = tmp_path / "python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")

    text_calls = []
    image_calls = []

    monkeypatch.setattr(runbook.live_comfy_smoke, "resolve_live_keys", lambda image2_key, banana_key: ("image-key", ""))
    monkeypatch.setattr(
        runbook,
        "choose_default_live_model",
        lambda image2_key, banana_key: ("gpt-image-2", ["selected model gpt-image-2 via image-2 visibility"]),
    )
    monkeypatch.setattr(
        runbook.live_comfy_smoke,
        "run_local_live_text_smoke",
        lambda **kwargs: text_calls.append(kwargs) or {
            "prompt_id": "text-123",
            "images": [{"filename": "text.png", "subfolder": "nanaix", "type": "output"}],
        },
    )
    monkeypatch.setattr(
        runbook.live_comfy_smoke,
        "run_local_live_image_smoke",
        lambda **kwargs: image_calls.append(kwargs) or {
            "prompt_id": "image-123",
            "images": [{"filename": "image.png", "subfolder": "nanaix", "type": "output"}],
        },
    )

    report = runbook.execute(
        custom_nodes=str(custom_nodes),
        comfy_python=str(python_executable),
        roots=[tmp_path],
        force=True,
        smoke_host="127.0.0.1",
        smoke_port=8191,
        smoke_timeout=45.0,
        run_smoke=True,
        resolve_custom_nodes_path=lambda custom_nodes, roots=None: Path(custom_nodes).resolve(),
        find_best_python=lambda roots=None: python_executable.resolve(),
        deploy_fn=lambda path, force=False: (True, "deployed"),
        verify_fn=lambda path: (True, "light ok"),
        verify_runtime_fn=lambda path, python_executable: (True, "runtime ok"),
        smoke_check_fn=lambda comfy_root, python_executable, host, port, timeout: runbook.RunbookReport(True, ["Registered nodes: Nanaix_Text, Nanaix_Image"]),
        multi_workflow_smoke_fn=lambda *args, **kwargs: [
            runbook.RunbookReport(True, ["Queued minimal_text_workflow.json"]),
            runbook.RunbookReport(True, ["Queued minimal_image_workflow.json"]),
        ],
        detect_live_keys_fn=lambda: True,
    )

    assert report.ok
    assert len(text_calls) == 1
    assert len(image_calls) == 1
    assert any("selected model gpt-image-2 via image-2 visibility" in line for line in report.lines)
    assert text_calls[0]["comfy_root"] == custom_nodes.resolve().parent
    assert image_calls[0]["host"] == "127.0.0.1"
    assert image_calls[0]["input_image_name"] == "workflow_smoke_input.png"
    assert any("Live ComfyUI smoke: mode=text" in line and "text.png" in line and "output/nanaix" in line for line in report.lines)
    assert any("Live ComfyUI smoke: mode=image" in line and "image.png" in line and "output/nanaix" in line for line in report.lines)


def test_choose_default_live_model_falls_back_to_visible_banana_model() -> None:
    model, lines = runbook.choose_default_live_model(
        image2_key="image-key",
        banana_key="banana-key",
        image2_models_fn=lambda key: ["gpt-image-1"],
        banana_models_fn=lambda key: ["nano-banana-2", "nano-banana-pro"],
    )

    assert model == "nano-banana-pro"
    assert any("gpt-image-2 is not visible" in line for line in lines)
    assert any("selected model nano-banana-pro" in line for line in lines)


def test_find_best_comfy_python_prefers_embedded_python(tmp_path: Path) -> None:
    embedded = tmp_path / "ComfyUI-aki-v3" / "python" / "python.exe"
    other = tmp_path / "tools" / "python.exe"
    embedded.parent.mkdir(parents=True)
    other.parent.mkdir(parents=True)
    embedded.write_text("", encoding="utf-8")
    other.write_text("", encoding="utf-8")

    result = runbook.find_best_comfy_python([tmp_path])

    assert result == embedded.resolve()
