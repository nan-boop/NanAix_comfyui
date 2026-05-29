from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from scripts import live_comfy_smoke


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class DummyProcess:
    def __init__(self) -> None:
        self.returncode = None

    def poll(self):
        return self.returncode


class ErrorResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return self.payload

    def close(self) -> None:
        return None


def test_build_text_prompt_includes_save_image_and_api_key() -> None:
    prompt = live_comfy_smoke.build_text_prompt(
        prompt_text="A red lantern on a rainy street",
        model="gpt-image-2",
        width=1024,
        height=1024,
        n=1,
        quality="high",
        output_format="png",
        background="transparent",
        style="vivid",
        moderation="auto",
        output_compression=60,
        partial_images=2,
        stream=True,
        api_key="image-key",
        filename_prefix="nanaix_live_test",
    )

    assert prompt["1"]["class_type"] == "Nanaix_Text"
    assert prompt["1"]["inputs"]["api_key"] == "image-key"
    assert prompt["1"]["inputs"]["background"] == "transparent"
    assert prompt["1"]["inputs"]["style"] == "vivid"
    assert prompt["1"]["inputs"]["moderation"] == "auto"
    assert prompt["1"]["inputs"]["output_compression"] == 60
    assert prompt["1"]["inputs"]["partial_images"] == 2
    assert prompt["1"]["inputs"]["stream"] is True
    assert prompt["2"]["class_type"] == "SaveImage"
    assert prompt["2"]["inputs"]["images"] == ["1", 0]
    assert prompt["2"]["inputs"]["filename_prefix"] == "nanaix_live_test"


def test_build_image_prompt_includes_load_image_nanaix_image_and_save_image() -> None:
    prompt = live_comfy_smoke.build_image_prompt(
        prompt_text="Turn this into a watercolor illustration",
        model="gpt-image-2",
        width=1024,
        height=1024,
        n=1,
        quality="high",
        output_format="png",
        background="auto",
        style="natural",
        moderation="low",
        output_compression=25,
        partial_images=4,
        stream=True,
        api_key="image-key",
        filename_prefix="nanaix_live_edit_test",
        input_image_name="live_input.png",
    )

    assert prompt["1"]["class_type"] == "LoadImage"
    assert prompt["1"]["inputs"]["image"] == "live_input.png"
    assert prompt["2"]["class_type"] == "Nanaix_Image"
    assert prompt["2"]["inputs"]["image_1"] == ["1", 0]
    assert prompt["2"]["inputs"]["api_key"] == "image-key"
    assert prompt["2"]["inputs"]["background"] == "auto"
    assert prompt["2"]["inputs"]["style"] == "natural"
    assert prompt["2"]["inputs"]["moderation"] == "low"
    assert prompt["2"]["inputs"]["output_compression"] == 25
    assert prompt["2"]["inputs"]["partial_images"] == 4
    assert prompt["2"]["inputs"]["stream"] is True
    assert prompt["3"]["class_type"] == "SaveImage"
    assert prompt["3"]["inputs"]["images"] == ["2", 0]
    assert prompt["3"]["inputs"]["filename_prefix"] == "nanaix_live_edit_test"


def test_wait_for_history_returns_save_image_outputs(monkeypatch) -> None:
    responses = iter(
        [
            {},
            {
                "prompt-123": {
                    "outputs": {
                        "2": {
                            "images": [
                                {
                                    "filename": "nanaix_live_test_00001_.png",
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
        live_comfy_smoke.request,
        "urlopen",
        lambda req, timeout=0: FakeResponse(next(responses)),
    )
    monkeypatch.setattr(live_comfy_smoke.time, "sleep", lambda _: None)

    result = live_comfy_smoke.wait_for_history("127.0.0.1", 8188, "prompt-123", timeout=5.0)

    assert result["outputs"]["2"]["images"][0]["filename"] == "nanaix_live_test_00001_.png"


def test_queue_prompt_wraps_http_error_with_response_detail(monkeypatch) -> None:
    def fake_urlopen(_request, timeout=0):
        raise HTTPError(
            url="http://127.0.0.1:8188/prompt",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=ErrorResponse(b'{"error":"missing prompt"}'),
        )

    monkeypatch.setattr(live_comfy_smoke.request, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError) as error:
        live_comfy_smoke.queue_prompt("127.0.0.1", 8188, {"1": {"class_type": "Nanaix_Text", "inputs": {}}})

    text = str(error.value)
    assert "/prompt" in text
    assert "HTTP 400" in text
    assert "missing prompt" in text


def test_extract_saved_images_from_history_returns_flat_list() -> None:
    history_payload = {
        "outputs": {
            "2": {
                "images": [
                    {"filename": "a.png", "subfolder": "", "type": "output"},
                    {"filename": "b.png", "subfolder": "x", "type": "output"},
                ]
            },
            "3": {"text": ["ignored"]},
        }
    }

    images = live_comfy_smoke.extract_saved_images_from_history(history_payload)

    assert images == [
        {"filename": "a.png", "subfolder": "", "type": "output"},
        {"filename": "b.png", "subfolder": "x", "type": "output"},
    ]


def test_resolve_live_keys_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv(live_comfy_smoke.IMAGE2_KEY_ENV, "env-image-key")
    monkeypatch.setenv(live_comfy_smoke.BANANA_KEY_ENV, "env-banana-key")

    image2_key, banana_key = live_comfy_smoke.resolve_live_keys("", "")

    assert image2_key == "env-image-key"
    assert banana_key == "env-banana-key"


def test_main_returns_zero_when_skipping_without_keys(monkeypatch, capsys) -> None:
    monkeypatch.delenv(live_comfy_smoke.IMAGE2_KEY_ENV, raising=False)
    monkeypatch.delenv(live_comfy_smoke.BANANA_KEY_ENV, raising=False)
    monkeypatch.setattr(
        live_comfy_smoke,
        "parse_args",
        lambda: type(
            "Args",
            (),
            {
                "host": "127.0.0.1",
                "port": 8188,
                "mode": "text",
                "model": "gpt-image-2",
                "prompt": "hello",
                "width": 1024,
                "height": 1024,
                "n": 1,
                "quality": "high",
                "output_format": "png",
                "filename_prefix": "nanaix_live_test",
                "image2_key": "",
                "banana_key": "",
                "timeout": 30.0,
                "fail_if_missing_key": False,
            },
        )(),
    )

    exit_code = live_comfy_smoke.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Skipping live ComfyUI smoke" in output
    assert "gpt-image-2" in output
    assert live_comfy_smoke.IMAGE2_KEY_ENV in output


def test_parse_args_accepts_local_launch_options(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "live_comfy_smoke.py",
            "--comfy-root",
            "F:/ComfyUI/ComfyUI",
            "--python",
            "F:/ComfyUI/python/python.exe",
            "--host",
            "127.0.0.1",
            "--port",
            "9001",
        ],
    )

    args = live_comfy_smoke.parse_args()

    assert args.comfy_root == "F:/ComfyUI/ComfyUI"
    assert args.python == "F:/ComfyUI/python/python.exe"
    assert args.host == "127.0.0.1"
    assert args.port == 9001


def test_parse_args_accepts_image_mode(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "live_comfy_smoke.py",
            "--mode",
            "image",
            "--input-image-name",
            "live_input.png",
        ],
    )

    args = live_comfy_smoke.parse_args()

    assert args.mode == "image"
    assert args.input_image_name == "live_input.png"


def test_main_uses_local_launch_when_comfy_paths_are_provided(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        live_comfy_smoke,
        "parse_args",
        lambda: type(
            "Args",
            (),
                {
                    "host": "127.0.0.1",
                    "port": 8188,
                    "model": "gpt-image-2",
                    "model_was_explicit": False,
                    "prompt": "hello",
                "width": 1024,
                "height": 1024,
                    "n": 1,
                    "quality": "high",
                    "output_format": "png",
                    "background": "auto",
                    "filename_prefix": "nanaix_live_test",
                    "image2_key": "image-key",
                    "banana_key": "banana-key",
                "timeout": 30.0,
                "fail_if_missing_key": False,
                "comfy_root": "F:/ComfyUI/ComfyUI",
                "python": "F:/ComfyUI/python/python.exe",
            },
        )(),
    )
    monkeypatch.setattr(
        live_comfy_smoke,
        "choose_live_model_for_keys",
        lambda image2_key, banana_key, preferred_model="gpt-image-2": ("nano-banana-pro", ["selected model nano-banana-pro"]),
    )
    monkeypatch.setattr(
        live_comfy_smoke,
        "run_local_live_text_smoke",
        lambda **kwargs: calls.append(kwargs) or {"prompt_id": "prompt-123", "images": [{"filename": "a.png"}]},
    )

    exit_code = live_comfy_smoke.main()

    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0]["model"] == "nano-banana-pro"
    assert calls[0]["comfy_root"] == Path("F:/ComfyUI/ComfyUI").resolve()
    assert calls[0]["python_executable"] == Path("F:/ComfyUI/python/python.exe").resolve()


def test_main_uses_local_image_launch_when_mode_is_image(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        live_comfy_smoke,
        "parse_args",
        lambda: type(
            "Args",
            (),
                {
                    "mode": "image",
                    "host": "127.0.0.1",
                    "port": 8188,
                "model": "gpt-image-2",
                "model_was_explicit": False,
                "prompt": "hello",
                "width": 1024,
                "height": 1024,
                    "n": 1,
                    "quality": "high",
                    "output_format": "png",
                    "background": "transparent",
                    "filename_prefix": "nanaix_live_edit_test",
                    "image2_key": "image-key",
                    "banana_key": "banana-key",
                "timeout": 30.0,
                "fail_if_missing_key": False,
                "comfy_root": "F:/ComfyUI/ComfyUI",
                "python": "F:/ComfyUI/python/python.exe",
                "input_image_name": "live_input.png",
            },
        )(),
    )
    monkeypatch.setattr(
        live_comfy_smoke,
        "choose_live_model_for_keys",
        lambda image2_key, banana_key, preferred_model="gpt-image-2": ("nano-banana-pro", ["selected model nano-banana-pro"]),
    )
    monkeypatch.setattr(
        live_comfy_smoke,
        "run_local_live_image_smoke",
        lambda **kwargs: calls.append(kwargs) or {"prompt_id": "prompt-image-123", "images": [{"filename": "a.png"}]},
    )

    exit_code = live_comfy_smoke.main()

    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0]["model"] == "nano-banana-pro"
    assert calls[0]["comfy_root"] == Path("F:/ComfyUI/ComfyUI").resolve()
    assert calls[0]["input_image_name"] == "live_input.png"


def test_main_returns_nonzero_and_prints_runtime_failures(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        live_comfy_smoke,
        "parse_args",
        lambda: type(
            "Args",
            (),
            {
                "mode": "text",
                "host": "127.0.0.1",
                "port": 8188,
                "model": "gpt-image-2",
                "model_was_explicit": True,
                "prompt": "hello",
                "width": 1024,
                "height": 1024,
                "n": 1,
                "quality": "high",
                "output_format": "png",
                "background": "auto",
                "style": "natural",
                "moderation": "auto",
                "output_compression": 0,
                "partial_images": 0,
                "stream": False,
                "filename_prefix": "nanaix_live_test",
                "image2_key": "image-key",
                "banana_key": "",
                "timeout": 30.0,
                "fail_if_missing_key": False,
                "comfy_root": "",
                "python": "",
            },
        )(),
    )
    monkeypatch.setattr(
        live_comfy_smoke,
        "run_live_text_smoke",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("ComfyUI /prompt failed with HTTP 400: missing prompt")),
    )

    exit_code = live_comfy_smoke.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "ComfyUI /prompt failed with HTTP 400: missing prompt" in output


def test_choose_live_model_for_keys_prefers_visible_image2_model() -> None:
    model, lines = live_comfy_smoke.choose_live_model_for_keys(
        image2_key="image-key",
        banana_key="banana-key",
        image2_models_fn=lambda key: ["gpt-image-2", "other-model"],
        banana_models_fn=lambda key: ["nano-banana-2", "nano-banana-pro"],
    )

    assert model == "gpt-image-2"
    assert any("selected model gpt-image-2" in line for line in lines)


def test_run_live_image_smoke_queues_image_prompt_and_waits_for_history(monkeypatch) -> None:
    queued = []
    waited = []
    monkeypatch.setattr(
        live_comfy_smoke,
        "queue_prompt",
        lambda host, port, prompt: queued.append((host, port, prompt)) or {"prompt_id": "prompt-image-123"},
    )
    monkeypatch.setattr(
        live_comfy_smoke,
        "wait_for_history",
        lambda host, port, prompt_id, timeout: waited.append((host, port, prompt_id, timeout))
        or {"outputs": {"3": {"images": [{"filename": "edit.png", "subfolder": "", "type": "output"}]}}},
    )

    result = live_comfy_smoke.run_live_image_smoke(
        host="127.0.0.1",
        port=8188,
        model="gpt-image-2",
        prompt_text="Turn this into a watercolor illustration",
        width=1024,
        height=1024,
        n=1,
        quality="high",
        output_format="png",
        background="transparent",
        style="vivid",
        moderation="auto",
        output_compression=50,
        partial_images=3,
        stream=True,
        filename_prefix="nanaix_live_edit_test",
        image2_key="image-key",
        banana_key="",
        timeout=30.0,
        input_image_name="live_input.png",
    )

    assert result["prompt_id"] == "prompt-image-123"
    assert len(result["images"]) == 1
    assert queued[0][2]["2"]["class_type"] == "Nanaix_Image"
    assert queued[0][2]["2"]["inputs"]["image_1"] == ["1", 0]
    assert waited == [("127.0.0.1", 8188, "prompt-image-123", 30.0)]


def test_run_live_text_smoke_warns_when_banana_ignores_image2_only_options(monkeypatch) -> None:
    monkeypatch.setattr(
        live_comfy_smoke,
        "queue_prompt",
        lambda host, port, prompt: {"prompt_id": "prompt-text-123"},
    )
    monkeypatch.setattr(
        live_comfy_smoke,
        "wait_for_history",
        lambda host, port, prompt_id, timeout: {"outputs": {"2": {"images": [{"filename": "text.png", "subfolder": "", "type": "output"}]}}},
    )

    with pytest.warns(UserWarning, match="ignored for nano-banana-pro"):
        result = live_comfy_smoke.run_live_text_smoke(
            host="127.0.0.1",
            port=8188,
            model="nano-banana-pro",
            prompt_text="hello",
            width=1024,
            height=1024,
            n=1,
            quality="high",
            output_format="png",
            background="transparent",
            style="vivid",
            moderation="low",
            output_compression=25,
            partial_images=2,
            stream=True,
            filename_prefix="nanaix_live_test",
            image2_key="",
            banana_key="banana-key",
            timeout=30.0,
        )

    assert result["prompt_id"] == "prompt-text-123"


def test_ensure_local_input_image_creates_missing_file(tmp_path: Path) -> None:
    comfy_root = tmp_path / "ComfyUI"

    target = live_comfy_smoke.ensure_local_input_image(
        comfy_root=comfy_root,
        input_image_name="live_input.png",
    )

    assert target == comfy_root / "input" / "live_input.png"
    assert target.exists()


def test_run_local_live_image_smoke_prepares_input_and_launches_local_comfy(monkeypatch, tmp_path: Path) -> None:
    comfy_root = tmp_path / "ComfyUI"
    python_executable = tmp_path / "python.exe"
    launches = []
    stops = []
    prepared = []
    process = DummyProcess()

    monkeypatch.setattr(
        live_comfy_smoke.comfyui_smoke,
        "launch_comfyui_process",
        lambda command, cwd: launches.append((command, cwd)) or process,
    )
    monkeypatch.setattr(
        live_comfy_smoke.comfyui_smoke,
        "probe_server_ready",
        lambda host, port: True,
    )
    monkeypatch.setattr(
        live_comfy_smoke.comfyui_smoke,
        "stop_process",
        lambda process: stops.append(process),
    )
    monkeypatch.setattr(
        live_comfy_smoke,
        "ensure_local_input_image",
        lambda comfy_root, input_image_name: prepared.append((comfy_root, input_image_name)) or comfy_root / "input" / input_image_name,
    )
    monkeypatch.setattr(
        live_comfy_smoke,
        "run_live_image_smoke",
        lambda **kwargs: {"prompt_id": "image-123", "images": [{"filename": "image.png"}], "history": {}},
    )

    result = live_comfy_smoke.run_local_live_image_smoke(
        comfy_root=comfy_root,
        python_executable=python_executable,
        host="127.0.0.1",
        port=8188,
        model="gpt-image-2",
        prompt_text="Turn this into a watercolor illustration",
        width=1024,
        height=1024,
        n=1,
        quality="high",
        output_format="png",
        background="auto",
        style="natural",
        moderation="low",
        output_compression=0,
        partial_images=0,
        stream=False,
        filename_prefix="nanaix_live_edit_test",
        image2_key="image-key",
        banana_key="",
        timeout=30.0,
        input_image_name="live_input.png",
    )

    assert result["prompt_id"] == "image-123"
    assert len(launches) == 1
    assert prepared == [(comfy_root, "live_input.png")]
    assert stops == [process]


def test_summarize_saved_images_includes_mode_and_output_location() -> None:
    summary = live_comfy_smoke.summarize_saved_images(
        mode="image",
        prompt_id="prompt-123",
        images=[
            {
                "filename": "edit_00001_.png",
                "subfolder": "nanaix",
                "type": "output",
            }
        ],
    )

    assert "mode=image" in summary
    assert "prompt_id=prompt-123" in summary
    assert "edit_00001_.png" in summary
    assert "output/nanaix" in summary
