from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError

from scripts import workflow_smoke


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class FakeHttpError(HTTPError):
    def __init__(self, url: str, code: int, msg: str, payload: dict) -> None:
        super().__init__(url, code, msg, hdrs=None, fp=None)
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class DummyProcess:
    def __init__(self) -> None:
        self.returncode = None

    def poll(self):
        return self.returncode


def test_build_prompt_payload_from_text_workflow(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "Nanaix_Text",
                        "widgets_values": [
                            "A red lantern on a rainy street",
                            "gpt-image-2",
                            "custom",
                            1024,
                            1024,
                            1,
                            "high",
                            "png",
                            "auto",
                            "vivid",
                            "auto",
                            50,
                            3,
                            True,
                            "",
                            "",
                        ],
                        "outputs": [{"name": "image", "type": "IMAGE", "links": [1]}],
                    },
                    {
                        "id": 2,
                        "type": "PreviewImage",
                        "inputs": [{"name": "images", "type": "IMAGE", "link": 1}],
                    },
                    {
                        "id": 3,
                        "type": "SaveImage",
                        "inputs": [{"name": "images", "type": "IMAGE", "link": 1}],
                        "widgets_values": ["nanaix_text_example"],
                    },
                ],
                "links": [
                    [1, 1, 0, 2, 0, "IMAGE"],
                    [2, 1, 0, 3, 0, "IMAGE"],
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = workflow_smoke.build_prompt_payload(workflow_path)

    assert "prompt" in payload
    assert payload["prompt"]["1"]["class_type"] == "Nanaix_Text"
    assert payload["prompt"]["1"]["inputs"]["prompt"] == "A red lantern on a rainy street"
    assert payload["prompt"]["1"]["inputs"]["resolution_preset"] == "custom"
    assert payload["prompt"]["1"]["inputs"]["background"] == "auto"
    assert payload["prompt"]["1"]["inputs"]["style"] == "vivid"
    assert payload["prompt"]["1"]["inputs"]["moderation"] == "auto"
    assert payload["prompt"]["1"]["inputs"]["output_compression"] == 50
    assert payload["prompt"]["1"]["inputs"]["partial_images"] == 3
    assert payload["prompt"]["1"]["inputs"]["stream"] is True
    assert payload["prompt"]["2"]["inputs"]["images"] == ["1", 0]
    assert payload["prompt"]["3"]["inputs"]["images"] == ["1", 0]
    assert payload["prompt"]["3"]["inputs"]["filename_prefix"] == "nanaix_text_example"


def test_build_prompt_payload_from_image_workflow(tmp_path: Path) -> None:
    workflow_path = tmp_path / "image_workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "LoadImage",
                        "widgets_values": ["workflow_smoke_input.png"],
                        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1]}],
                    },
                    {
                        "id": 2,
                        "type": "Nanaix_Image",
                        "inputs": [{"name": "image_1", "type": "IMAGE", "link": 1}],
                        "widgets_values": [
                            "Turn this into a watercolor illustration",
                            "gpt-image-2",
                            "custom",
                            1024,
                            1024,
                            1,
                            "high",
                            "png",
                            "transparent",
                            "natural",
                            "low",
                            80,
                            2,
                            True,
                            "",
                            "",
                        ],
                        "outputs": [{"name": "image", "type": "IMAGE", "links": [2]}],
                    },
                    {
                        "id": 3,
                        "type": "PreviewImage",
                        "inputs": [{"name": "images", "type": "IMAGE", "link": 2}],
                    },
                    {
                        "id": 4,
                        "type": "SaveImage",
                        "inputs": [{"name": "images", "type": "IMAGE", "link": 2}],
                        "widgets_values": ["nanaix_image_example"],
                    },
                ],
                "links": [
                    [1, 1, 0, 2, 0, "IMAGE"],
                    [2, 2, 0, 3, 0, "IMAGE"],
                    [3, 2, 0, 4, 0, "IMAGE"],
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = workflow_smoke.build_prompt_payload(workflow_path)

    assert payload["prompt"]["2"]["class_type"] == "Nanaix_Image"
    assert payload["prompt"]["1"]["inputs"]["image"] == "workflow_smoke_input.png"
    assert payload["prompt"]["2"]["inputs"]["prompt"] == "Turn this into a watercolor illustration"
    assert payload["prompt"]["2"]["inputs"]["resolution_preset"] == "custom"
    assert payload["prompt"]["2"]["inputs"]["background"] == "transparent"
    assert payload["prompt"]["2"]["inputs"]["style"] == "natural"
    assert payload["prompt"]["2"]["inputs"]["moderation"] == "low"
    assert payload["prompt"]["2"]["inputs"]["output_compression"] == 80
    assert payload["prompt"]["2"]["inputs"]["partial_images"] == 2
    assert payload["prompt"]["2"]["inputs"]["stream"] is True
    assert payload["prompt"]["2"]["inputs"]["image_1"] == ["1", 0]
    assert payload["prompt"]["3"]["inputs"]["images"] == ["2", 0]
    assert payload["prompt"]["4"]["inputs"]["images"] == ["2", 0]
    assert payload["prompt"]["4"]["inputs"]["filename_prefix"] == "nanaix_image_example"


def test_build_prompt_payload_from_multi_image_workflow(tmp_path: Path) -> None:
    workflow_path = tmp_path / "multi_image_workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "LoadImage",
                        "widgets_values": ["workflow_smoke_input.png"],
                        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1]}],
                    },
                    {
                        "id": 2,
                        "type": "LoadImage",
                        "widgets_values": ["workflow_smoke_input_2.png"],
                        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [2]}],
                    },
                    {
                        "id": 3,
                        "type": "Nanaix_Image",
                        "inputs": [
                            {"name": "image_1", "type": "IMAGE", "link": 1},
                            {"name": "image_2", "type": "IMAGE", "link": 2},
                        ],
                        "widgets_values": [
                            "Blend the two references into one cinematic composition",
                            "gpt-image-2",
                            "custom",
                            1024,
                            1024,
                            1,
                            "high",
                            "png",
                            "auto",
                            "natural",
                            "auto",
                            0,
                            0,
                            False,
                            "",
                            "",
                        ],
                        "outputs": [{"name": "image", "type": "IMAGE", "links": [3]}],
                    },
                    {
                        "id": 4,
                        "type": "PreviewImage",
                        "inputs": [{"name": "images", "type": "IMAGE", "link": 3}],
                    },
                    {
                        "id": 5,
                        "type": "SaveImage",
                        "inputs": [{"name": "images", "type": "IMAGE", "link": 3}],
                        "widgets_values": ["nanaix_multi_image_example"],
                    },
                ],
                "links": [
                    [1, 1, 0, 3, 0, "IMAGE"],
                    [2, 2, 0, 3, 1, "IMAGE"],
                    [3, 3, 0, 4, 0, "IMAGE"],
                    [4, 3, 0, 5, 0, "IMAGE"],
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = workflow_smoke.build_prompt_payload(workflow_path)

    assert payload["prompt"]["1"]["inputs"]["image"] == "workflow_smoke_input.png"
    assert payload["prompt"]["2"]["inputs"]["image"] == "workflow_smoke_input_2.png"
    assert payload["prompt"]["3"]["class_type"] == "Nanaix_Image"
    assert payload["prompt"]["3"]["inputs"]["image_1"] == ["1", 0]
    assert payload["prompt"]["3"]["inputs"]["image_2"] == ["2", 0]
    assert payload["prompt"]["4"]["inputs"]["images"] == ["3", 0]
    assert payload["prompt"]["5"]["inputs"]["images"] == ["3", 0]
    assert payload["prompt"]["5"]["inputs"]["filename_prefix"] == "nanaix_multi_image_example"


def test_queue_prompt_returns_prompt_id_and_node_errors(monkeypatch) -> None:
    def fake_urlopen(request_obj, timeout=0):
        assert request_obj.full_url == "http://127.0.0.1:8188/prompt"
        body = json.loads(request_obj.data.decode("utf-8"))
        assert "prompt" in body
        return FakeResponse({"prompt_id": "prompt-123", "node_errors": {"1": {"errors": []}}})

    monkeypatch.setattr(workflow_smoke.request, "urlopen", fake_urlopen)

    result = workflow_smoke.queue_prompt("127.0.0.1", 8188, {"prompt": {"1": {"class_type": "Nanaix_Text", "inputs": {}}}})

    assert result["prompt_id"] == "prompt-123"
    assert "1" in result["node_errors"]


def test_queue_prompt_rejects_missing_prompt_id(monkeypatch) -> None:
    def fake_urlopen(request_obj, timeout=0):
        return FakeResponse({"node_errors": {}})

    monkeypatch.setattr(workflow_smoke.request, "urlopen", fake_urlopen)

    try:
        workflow_smoke.queue_prompt("127.0.0.1", 8188, {"prompt": {"1": {"class_type": "Nanaix_Text", "inputs": {}}}})
    except RuntimeError as error:
        assert "prompt_id" in str(error)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected queue_prompt to fail when prompt_id is missing")


def test_queue_prompt_wraps_connection_errors(monkeypatch) -> None:
    def fake_urlopen(request_obj, timeout=0):
        raise URLError("connection refused")

    monkeypatch.setattr(workflow_smoke.request, "urlopen", fake_urlopen)

    try:
        workflow_smoke.queue_prompt("127.0.0.1", 8188, {"prompt": {"1": {"class_type": "Nanaix_Text", "inputs": {}}}})
    except RuntimeError as error:
        assert "Could not reach ComfyUI /prompt" in str(error)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected queue_prompt to fail when ComfyUI is not reachable")


def test_queue_prompt_wraps_timeout_errors(monkeypatch) -> None:
    def fake_urlopen(request_obj, timeout=0):
        raise TimeoutError("timed out")

    monkeypatch.setattr(workflow_smoke.request, "urlopen", fake_urlopen)

    try:
        workflow_smoke.queue_prompt("127.0.0.1", 8188, {"prompt": {"1": {"class_type": "Nanaix_Text", "inputs": {}}}})
    except RuntimeError as error:
        assert "Could not reach ComfyUI /prompt" in str(error)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected queue_prompt to fail when ComfyUI times out")


def test_queue_prompt_includes_http_error_body_details(monkeypatch) -> None:
    def fake_urlopen(request_obj, timeout=0):
        raise FakeHttpError(
            request_obj.full_url,
            503,
            "Service Unavailable",
            {
                "error": "backend overloaded",
            },
        )

    monkeypatch.setattr(workflow_smoke.request, "urlopen", fake_urlopen)

    try:
        workflow_smoke.queue_prompt("127.0.0.1", 8188, {"prompt": {"1": {"class_type": "Nanaix_Text", "inputs": {}}}})
    except RuntimeError as error:
        text = str(error)
        assert "ComfyUI /prompt returned HTTP 503" in text
        assert "backend overloaded" in text
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected queue_prompt to include HTTP response body details")


def test_queue_prompt_accepts_validation_error_response_with_node_errors(monkeypatch) -> None:
    def fake_urlopen(request_obj, timeout=0):
        raise FakeHttpError(
            request_obj.full_url,
            400,
            "Bad Request",
            {
                "error": {"type": "prompt_outputs_failed_validation", "message": "Prompt outputs failed validation"},
                "node_errors": {"1": {"errors": [{"type": "custom_validation_failed"}]}},
            },
        )

    monkeypatch.setattr(workflow_smoke.request, "urlopen", fake_urlopen)

    result = workflow_smoke.queue_prompt("127.0.0.1", 8188, {"prompt": {"1": {"class_type": "Nanaix_Text", "inputs": {}}}})

    assert result["prompt_id"] == "validation_failed"
    assert "1" in result["node_errors"]


def test_wait_for_history_returns_prompt_payload(monkeypatch) -> None:
    responses = iter(
        [
            {},
            {
                "prompt-123": {
                    "outputs": {
                        "3": {
                            "images": [
                                {
                                    "filename": "nanaix_text_example_00001_.png",
                                    "subfolder": "",
                                    "type": "output",
                                }
                            ]
                        }
                    }
                }
            },
        ]
    )

    monkeypatch.setattr(
        workflow_smoke.request,
        "urlopen",
        lambda req, timeout=0: FakeResponse(next(responses)),
    )
    monkeypatch.setattr(workflow_smoke.time, "sleep", lambda _: None)

    result = workflow_smoke.wait_for_history("127.0.0.1", 8188, "prompt-123", timeout=5.0)

    assert result["outputs"]["3"]["images"][0]["filename"] == "nanaix_text_example_00001_.png"


def test_extract_saved_images_from_history_returns_flat_list() -> None:
    history_payload = {
        "outputs": {
            "3": {
                "images": [
                    {"filename": "a.png", "subfolder": "", "type": "output"},
                    {"filename": "b.png", "subfolder": "nested", "type": "output"},
                ]
            },
            "2": {"text": ["ignored"]},
        }
    }

    images = workflow_smoke.extract_saved_images_from_history(history_payload)

    assert images == [
        {"filename": "a.png", "subfolder": "", "type": "output"},
        {"filename": "b.png", "subfolder": "nested", "type": "output"},
    ]


def test_text_workflow_validation_failure_payload_can_be_single_error_anchor(monkeypatch) -> None:
    payload_holder: dict[str, dict] = {}

    def fake_urlopen(request_obj, timeout=0):
        payload_holder.update(json.loads(request_obj.data.decode("utf-8")))
        return FakeResponse(
            {
                "prompt_id": "validation_failed",
                "node_errors": {
                    "1": {
                        "errors": [
                            {
                                "type": "custom_validation_failed",
                                "message": "Custom validation failed for node",
                                "details": "prompt_graph - gpt-image-2 requires image2_api_key. Paste your image-2 key into the node. Saved config only pre-fills new nodes; a blank visible key is still treated as missing.",
                                "extra_info": {"input_name": "prompt_graph"},
                            }
                        ]
                    }
                },
            }
        )

    monkeypatch.setattr(workflow_smoke.request, "urlopen", fake_urlopen)

    result = workflow_smoke.queue_prompt(
        "127.0.0.1",
        8188,
        {
            "prompt": {
                "1": {
                    "class_type": "Nanaix_Text",
                    "inputs": {
                        "prompt": "hello",
                        "model": "gpt-image-2",
                        "image2_api_key": "",
                        "banana_api_key": "",
                    },
                }
            }
        },
    )

    assert result["prompt_id"] == "validation_failed"
    errors = result["node_errors"]["1"]["errors"]
    assert len(errors) == 1
    assert errors[0]["extra_info"]["input_name"] == "prompt_graph"
    assert payload_holder["prompt"]["1"]["inputs"]["image2_api_key"] == ""


def test_submit_text_workflow_smoke_uses_default_example(monkeypatch, tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "Nanaix_Text",
                        "widgets_values": [
                            "A red lantern on a rainy street",
                            "gpt-image-2",
                            1024,
                            1024,
                            1,
                            "high",
                            "png",
                            "",
                            "",
                        ],
                        "outputs": [{"name": "image", "type": "IMAGE", "links": [1]}],
                    }
                ],
                "links": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(workflow_smoke, "DEFAULT_TEXT_WORKFLOW_PATH", workflow_path)
    monkeypatch.setattr(
        workflow_smoke,
        "queue_prompt",
        lambda host, port, payload: {"prompt_id": "prompt-123", "node_errors": {}},
    )

    report = workflow_smoke.submit_text_workflow_smoke(host="127.0.0.1", port=8188)

    assert report.ok
    assert any("prompt-123" in line for line in report.lines)


def test_submit_workflow_smoke_can_verify_saved_images_when_requested(monkeypatch, tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "Nanaix_Text",
                        "widgets_values": [
                            "A red lantern on a rainy street",
                            "gpt-image-2",
                            1024,
                            1024,
                            1,
                            "high",
                            "png",
                            "",
                            "",
                        ],
                        "outputs": [{"name": "image", "type": "IMAGE", "links": [1]}],
                    },
                    {
                        "id": 2,
                        "type": "SaveImage",
                        "inputs": [{"name": "images", "type": "IMAGE", "link": 1}],
                        "widgets_values": ["nanaix_text_example"],
                    },
                ],
                "links": [[1, 1, 0, 2, 0, "IMAGE"]],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        workflow_smoke,
        "queue_prompt",
        lambda host, port, payload: {"prompt_id": "prompt-123", "node_errors": {}},
    )
    monkeypatch.setattr(
        workflow_smoke,
        "wait_for_history",
        lambda host, port, prompt_id, timeout: {
            "outputs": {
                "2": {
                    "images": [
                        {
                            "filename": "nanaix_text_example_00001_.png",
                            "subfolder": "",
                            "type": "output",
                        }
                    ]
                }
            }
        },
    )

    report = workflow_smoke.submit_workflow_smoke(
        host="127.0.0.1",
        port=8188,
        workflow_path=workflow_path,
        verify_saved_images=True,
        timeout=30.0,
    )

    assert report.ok
    assert any("Queued workflow prompt_id: prompt-123" in line for line in report.lines)
    assert any("Saved images: 1" in line for line in report.lines)
    assert any("First saved image: nanaix_text_example_00001_.png" in line for line in report.lines)


def test_submit_workflow_smoke_fails_when_saved_image_verification_finds_no_outputs(monkeypatch, tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "Nanaix_Text",
                        "widgets_values": [
                            "A red lantern on a rainy street",
                            "gpt-image-2",
                            1024,
                            1024,
                            1,
                            "high",
                            "png",
                            "",
                            "",
                        ],
                    }
                ],
                "links": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        workflow_smoke,
        "queue_prompt",
        lambda host, port, payload: {"prompt_id": "prompt-123", "node_errors": {}},
    )
    monkeypatch.setattr(
        workflow_smoke,
        "wait_for_history",
        lambda host, port, prompt_id, timeout: {"outputs": {}},
    )

    report = workflow_smoke.submit_workflow_smoke(
        host="127.0.0.1",
        port=8188,
        workflow_path=workflow_path,
        verify_saved_images=True,
        timeout=30.0,
    )

    assert not report.ok
    assert any("completed without saved output images" in line for line in report.lines)


def test_parse_args_accepts_verify_saved_images_flag(monkeypatch) -> None:
    monkeypatch.setattr(
        workflow_smoke.sys,
        "argv",
        ["workflow_smoke.py", "--verify-saved-images"],
    )

    args = workflow_smoke.parse_args()

    assert args.verify_saved_images is True


def test_submit_text_workflow_smoke_forwards_verify_saved_images(monkeypatch, tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(json.dumps({"nodes": [], "links": []}), encoding="utf-8")
    calls = []

    monkeypatch.setattr(
        workflow_smoke,
        "submit_workflow_smoke",
        lambda **kwargs: calls.append(kwargs)
        or workflow_smoke.WorkflowSmokeReport(True, ["Queued workflow prompt_id: prompt-123"]),
    )

    report = workflow_smoke.submit_text_workflow_smoke(
        host="127.0.0.1",
        port=8188,
        workflow_path=workflow_path,
        verify_saved_images=True,
    )

    assert report.ok
    assert calls == [
        {
            "host": "127.0.0.1",
            "port": 8188,
            "workflow_path": workflow_path,
            "comfy_root": None,
            "python_executable": None,
            "timeout": 30.0,
            "verify_saved_images": True,
        }
    ]


def test_main_returns_nonzero_and_prints_message_on_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr(workflow_smoke, "parse_args", lambda: type("Args", (), {"host": "127.0.0.1", "port": 8188, "workflow": "workflow.json"})())

    def fail_submit(**kwargs):
        raise RuntimeError("Could not reach ComfyUI /prompt")

    monkeypatch.setattr(workflow_smoke, "submit_workflow_smoke", fail_submit)

    exit_code = workflow_smoke.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Could not reach ComfyUI /prompt" in captured.out


def test_main_forwards_verify_saved_images_flag(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        workflow_smoke,
        "parse_args",
        lambda: type(
            "Args",
            (),
            {
                "host": "127.0.0.1",
                "port": 8188,
                "workflow": "workflow.json",
                "comfy_root": "",
                "python": "",
                "timeout": 30.0,
                "verify_saved_images": True,
            },
        )(),
    )
    monkeypatch.setattr(
        workflow_smoke,
        "submit_workflow_smoke",
        lambda **kwargs: calls.append(kwargs)
        or workflow_smoke.WorkflowSmokeReport(True, ["Queued workflow prompt_id: prompt-123"]),
    )
    monkeypatch.setattr(workflow_smoke, "safe_print_report", lambda text: None)

    exit_code = workflow_smoke.main()

    assert exit_code == 0
    assert calls == [
        {
            "host": "127.0.0.1",
            "port": 8188,
            "workflow_path": Path("workflow.json").resolve(),
            "verify_saved_images": True,
        }
    ]


def test_safe_print_report_falls_back_when_stdout_encoding_cannot_encode_text(monkeypatch) -> None:
    written: list[str] = []

    class FakeStdout:
        encoding = "gbk"

        def write(self, text: str) -> int:
            text.encode(self.encoding)
            written.append(text)
            return len(text)

        def flush(self) -> None:
            return None

    monkeypatch.setattr(workflow_smoke.sys, "stdout", FakeStdout())

    workflow_smoke.safe_print_report("contains weird char \u0368")

    assert written
    assert "contains weird char" in written[0]
    assert "?" in written[0]


def test_submit_text_workflow_smoke_can_use_local_launch(monkeypatch, tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "Nanaix_Text",
                        "widgets_values": [
                            "A red lantern on a rainy street",
                            "gpt-image-2",
                            1024,
                            1024,
                            1,
                            "high",
                            "png",
                            "",
                            "",
                        ],
                        "outputs": [{"name": "image", "type": "IMAGE", "links": [1]}],
                    }
                ],
                "links": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        workflow_smoke,
        "run_local_prompt_smoke",
        lambda workflow_path, comfy_root, python_executable, host, port, timeout, verify_saved_images=False: workflow_smoke.WorkflowSmokeReport(
            True,
            ["Queued workflow prompt_id: prompt-123", 'Node errors: {"1": {"errors": []}}'],
        ),
    )

    report = workflow_smoke.submit_text_workflow_smoke(
        host="127.0.0.1",
        port=8188,
        workflow_path=workflow_path,
        comfy_root=Path("F:/ComfyUI"),
        python_executable=Path("F:/ComfyUI/python.exe"),
        timeout=30.0,
    )

    assert report.ok
    assert any("prompt-123" in line for line in report.lines)


def test_submit_workflow_smoke_forwards_verify_saved_images_to_local_launch(monkeypatch, tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(json.dumps({"nodes": [], "links": []}), encoding="utf-8")
    calls = []

    monkeypatch.setattr(
        workflow_smoke,
        "run_local_prompt_smoke",
        lambda workflow_path, comfy_root, python_executable, host, port, timeout, verify_saved_images=False: calls.append(
            {
                "workflow_path": workflow_path,
                "comfy_root": comfy_root,
                "python_executable": python_executable,
                "host": host,
                "port": port,
                "timeout": timeout,
                "verify_saved_images": verify_saved_images,
            }
        )
        or workflow_smoke.WorkflowSmokeReport(True, ["Queued workflow prompt_id: prompt-123"]),
    )

    report = workflow_smoke.submit_workflow_smoke(
        host="127.0.0.1",
        port=8188,
        workflow_path=workflow_path,
        comfy_root=Path("F:/ComfyUI"),
        python_executable=Path("F:/ComfyUI/python.exe"),
        timeout=30.0,
        verify_saved_images=True,
    )

    assert report.ok
    assert calls == [
        {
            "workflow_path": workflow_path,
            "comfy_root": Path("F:/ComfyUI"),
            "python_executable": Path("F:/ComfyUI/python.exe"),
            "host": "127.0.0.1",
            "port": 8188,
            "timeout": 30.0,
            "verify_saved_images": True,
        }
    ]


def test_submit_workflow_smoke_uses_image_example(monkeypatch, tmp_path: Path) -> None:
    workflow_path = tmp_path / "image_workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "LoadImage",
                        "widgets_values": ["workflow_smoke_input.png"],
                        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1]}],
                    },
                    {
                        "id": 2,
                        "type": "Nanaix_Image",
                        "inputs": [{"name": "image_1", "type": "IMAGE", "link": 1}],
                        "widgets_values": [
                            "Turn this into a watercolor illustration",
                            "gpt-image-2",
                            1024,
                            1024,
                            1,
                            "high",
                            "png",
                            "",
                            "",
                        ],
                        "outputs": [{"name": "image", "type": "IMAGE", "links": [2]}],
                    },
                ],
                "links": [[1, 1, 0, 2, 0, "IMAGE"]],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        workflow_smoke,
        "queue_prompt",
        lambda host, port, payload: {"prompt_id": "prompt-image-123", "node_errors": {}},
    )

    report = workflow_smoke.submit_workflow_smoke(
        host="127.0.0.1",
        port=8188,
        workflow_path=workflow_path,
    )

    assert report.ok
    assert any("prompt-image-123" in line for line in report.lines)


def test_run_local_prompt_smoke_can_verify_saved_images(monkeypatch, tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "Nanaix_Text",
                        "widgets_values": [
                            "A red lantern on a rainy street",
                            "gpt-image-2",
                            1024,
                            1024,
                            1,
                            "high",
                            "png",
                            "",
                            "",
                        ],
                    },
                    {
                        "id": 2,
                        "type": "SaveImage",
                        "inputs": [{"name": "images", "type": "IMAGE", "link": 1}],
                        "widgets_values": ["nanaix_text_example"],
                    },
                ],
                "links": [[1, 1, 0, 2, 0, "IMAGE"]],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        workflow_smoke.comfyui_smoke,
        "launch_comfyui_process",
        lambda command, cwd: DummyProcess(),
    )
    monkeypatch.setattr(
        workflow_smoke.comfyui_smoke,
        "probe_server_ready",
        lambda host, port: True,
    )
    monkeypatch.setattr(
        workflow_smoke.comfyui_smoke,
        "stop_process",
        lambda process: None,
    )
    monkeypatch.setattr(
        workflow_smoke,
        "queue_prompt",
        lambda host, port, payload: {"prompt_id": "prompt-123", "node_errors": {}},
    )
    monkeypatch.setattr(
        workflow_smoke,
        "wait_for_history",
        lambda host, port, prompt_id, timeout: {
            "outputs": {
                "2": {
                    "images": [
                        {"filename": "nanaix_text_example_00001_.png", "subfolder": "", "type": "output"}
                    ]
                }
            }
        },
    )

    report = workflow_smoke.run_local_prompt_smoke(
        workflow_path=workflow_path,
        comfy_root=tmp_path / "ComfyUI",
        python_executable=Path("F:/ComfyUI/python.exe"),
        host="127.0.0.1",
        port=8188,
        timeout=30.0,
        verify_saved_images=True,
    )

    assert report.ok
    assert any("Saved images: 1" in line for line in report.lines)
    assert any("First saved image: nanaix_text_example_00001_.png" in line for line in report.lines)


def test_prepare_local_workflow_inputs_creates_missing_load_image_file(tmp_path: Path) -> None:
    workflow_path = tmp_path / "minimal_image_workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "LoadImage",
                        "widgets_values": ["workflow_smoke_input.png"],
                        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1]}],
                    },
                    {
                        "id": 2,
                        "type": "Nanaix_Image",
                        "inputs": [{"name": "image_1", "type": "IMAGE", "link": 1}],
                        "widgets_values": [
                            "Turn this into a watercolor illustration",
                            "gpt-image-2",
                            1024,
                            1024,
                            1,
                            "high",
                            "png",
                            "",
                            "",
                        ],
                    },
                ],
                "links": [[1, 1, 0, 2, 0, "IMAGE"]],
            }
        ),
        encoding="utf-8",
    )
    payload = workflow_smoke.build_prompt_payload(workflow_path)
    comfy_root = tmp_path / "ComfyUI"

    prepared = workflow_smoke.prepare_local_workflow_inputs(workflow_path, payload, comfy_root)

    assert len(prepared) == 1
    assert prepared[0].name == "workflow_smoke_input.png"
    assert prepared[0].exists()


def test_submit_multiple_workflow_smokes_reuses_one_local_process(monkeypatch, tmp_path: Path) -> None:
    text_workflow = tmp_path / "text_workflow.json"
    text_workflow.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "Nanaix_Text",
                        "widgets_values": [
                            "A red lantern on a rainy street",
                            "gpt-image-2",
                            1024,
                            1024,
                            1,
                            "high",
                            "png",
                            "",
                            "",
                        ],
                    }
                ],
                "links": [],
            }
        ),
        encoding="utf-8",
    )
    image_workflow = tmp_path / "image_workflow.json"
    image_workflow.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "LoadImage",
                        "widgets_values": ["workflow_smoke_input.png"],
                        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1]}],
                    },
                    {
                        "id": 2,
                        "type": "Nanaix_Image",
                        "inputs": [{"name": "image_1", "type": "IMAGE", "link": 1}],
                        "widgets_values": [
                            "Turn this into a watercolor illustration",
                            "gpt-image-2",
                            1024,
                            1024,
                            1,
                            "high",
                            "png",
                            "",
                            "",
                        ],
                    },
                ],
                "links": [[1, 1, 0, 2, 0, "IMAGE"]],
            }
        ),
        encoding="utf-8",
    )
    launches = []
    queued_payloads = []
    stopped = []
    readiness_checks = {"count": 0}

    monkeypatch.setattr(
        workflow_smoke.comfyui_smoke,
        "launch_comfyui_process",
        lambda command, cwd: launches.append((command, cwd)) or DummyProcess(),
    )
    monkeypatch.setattr(
        workflow_smoke,
        "queue_prompt",
        lambda host, port, payload: queued_payloads.append(payload) or {"prompt_id": f"prompt-{len(queued_payloads)}", "node_errors": {}},
    )
    monkeypatch.setattr(
        workflow_smoke.comfyui_smoke,
        "stop_process",
        lambda process: stopped.append(process),
    )
    monkeypatch.setattr(
        workflow_smoke.comfyui_smoke,
        "probe_server_ready",
        lambda host, port: readiness_checks.__setitem__("count", readiness_checks["count"] + 1) or True,
    )

    reports = workflow_smoke.submit_multiple_workflow_smokes(
        workflow_paths=[text_workflow, image_workflow],
        comfy_root=tmp_path / "ComfyUI",
        python_executable=Path("F:/ComfyUI/python.exe"),
        host="127.0.0.1",
        port=8188,
        timeout=30.0,
    )

    assert len(launches) == 1
    assert readiness_checks["count"] >= 1
    assert len(queued_payloads) == 2
    assert len(reports) == 2
    assert all(report.ok for report in reports)
    assert len(stopped) == 1


def test_submit_multiple_workflow_smokes_can_verify_saved_images(monkeypatch, tmp_path: Path) -> None:
    text_workflow = tmp_path / "text_workflow.json"
    text_workflow.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "Nanaix_Text",
                        "widgets_values": [
                            "A red lantern on a rainy street",
                            "gpt-image-2",
                            1024,
                            1024,
                            1,
                            "high",
                            "png",
                            "",
                            "",
                        ],
                    },
                    {
                        "id": 2,
                        "type": "SaveImage",
                        "inputs": [{"name": "images", "type": "IMAGE", "link": 1}],
                        "widgets_values": ["nanaix_text_example"],
                    },
                ],
                "links": [[1, 1, 0, 2, 0, "IMAGE"]],
            }
        ),
        encoding="utf-8",
    )
    image_workflow = tmp_path / "image_workflow.json"
    image_workflow.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "LoadImage",
                        "widgets_values": ["workflow_smoke_input.png"],
                        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1]}],
                    },
                    {
                        "id": 2,
                        "type": "Nanaix_Image",
                        "inputs": [{"name": "image_1", "type": "IMAGE", "link": 1}],
                        "widgets_values": [
                            "Turn this into a watercolor illustration",
                            "gpt-image-2",
                            1024,
                            1024,
                            1,
                            "high",
                            "png",
                            "",
                            "",
                        ],
                    },
                    {
                        "id": 3,
                        "type": "SaveImage",
                        "inputs": [{"name": "images", "type": "IMAGE", "link": 2}],
                        "widgets_values": ["nanaix_image_example"],
                    },
                ],
                "links": [
                    [1, 1, 0, 2, 0, "IMAGE"],
                    [2, 2, 0, 3, 0, "IMAGE"],
                ],
            }
        ),
        encoding="utf-8",
    )
    stopped = []

    monkeypatch.setattr(
        workflow_smoke.comfyui_smoke,
        "launch_comfyui_process",
        lambda command, cwd: DummyProcess(),
    )
    monkeypatch.setattr(
        workflow_smoke.comfyui_smoke,
        "probe_server_ready",
        lambda host, port: True,
    )
    monkeypatch.setattr(
        workflow_smoke.comfyui_smoke,
        "stop_process",
        lambda process: stopped.append(process),
    )

    queued_prompt_ids = iter(["prompt-1", "prompt-2"])
    monkeypatch.setattr(
        workflow_smoke,
        "queue_prompt",
        lambda host, port, payload: {"prompt_id": next(queued_prompt_ids), "node_errors": {}},
    )

    histories = {
        "prompt-1": {
            "outputs": {
                "2": {
                    "images": [
                        {"filename": "nanaix_text_example_00001_.png", "subfolder": "", "type": "output"}
                    ]
                }
            }
        },
        "prompt-2": {
            "outputs": {
                "3": {
                    "images": [
                        {"filename": "nanaix_image_example_00001_.png", "subfolder": "edited", "type": "output"}
                    ]
                }
            }
        },
    }
    monkeypatch.setattr(
        workflow_smoke,
        "wait_for_history",
        lambda host, port, prompt_id, timeout: histories[prompt_id],
    )

    reports = workflow_smoke.submit_multiple_workflow_smokes(
        workflow_paths=[text_workflow, image_workflow],
        comfy_root=tmp_path / "ComfyUI",
        python_executable=Path("F:/ComfyUI/python.exe"),
        host="127.0.0.1",
        port=8188,
        timeout=30.0,
        verify_saved_images=True,
    )

    assert len(reports) == 2
    assert all(report.ok for report in reports)
    assert any("Saved images: 1" in line for line in reports[0].lines)
    assert any("First saved image: nanaix_text_example_00001_.png" in line for line in reports[0].lines)
    assert any("Saved image location: output/edited" in line for line in reports[1].lines)
    assert not any("Prepared workflow input:" in line for line in reports[0].lines)
    assert any("Prepared workflow input:" in line for line in reports[1].lines)
    assert len(stopped) == 1
