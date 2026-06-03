from __future__ import annotations

import json
from urllib.error import HTTPError

import pytest
import torch
from PIL import Image

from services.banana_client import BananaClient
from services.image2_client import Image2Client
from utils.errors import NanaixNodeError
from utils.image_io import base64_to_pil_image, pil_image_to_base64, tensor_image_to_pil


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return self.payload

    def close(self) -> None:
        return None

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_image2_response_to_tensors_decodes_b64_image() -> None:
    image = torch.zeros((4, 4, 3), dtype=torch.float32)
    encoded = pil_image_to_base64(tensor_image_to_pil(image))

    tensors = Image2Client._response_to_tensors(
        {"data": [{"b64_json": encoded}]},
        stage="generation decode",
        node_name="Nanaix_Text",
    )

    assert len(tensors) == 1
    assert tensors[0].shape == (4, 4, 3)


def test_image2_list_models_reads_model_ids(monkeypatch) -> None:
    client = Image2Client("image-key")
    monkeypatch.setattr(
        client,
        "_get_request",
        lambda path, stage, node_name: {
            "data": [
                {"id": "gpt-image-2"},
                {"id": "gpt-image-3"},
            ]
        },
    )

    models = client.list_models(node_name="SmokeTest")

    assert models == ["gpt-image-2", "gpt-image-3"]


def test_image2_edit_builds_json_images_payload(monkeypatch) -> None:
    client = Image2Client("image-key")
    captured: dict[str, object] = {}

    def fake_json_request(path, payload, stage, node_name, model):
        captured["path"] = path
        captured["payload"] = payload
        encoded = payload["images"][0]["image_url"].split(",", 1)[1]
        return {"data": [{"b64_json": encoded}]}

    monkeypatch.setattr(client, "_json_request", fake_json_request)

    results = client.edit(
        node_name="Nanaix_Image",
        prompt="edit",
        model="gpt-image-2",
        size="1024x1024",
        n=1,
        quality="high",
        output_format="png",
        background="transparent",
        style="vivid",
        moderation="auto",
        output_compression=70,
        partial_images=2,
        stream=False,
        reference_images=[
            torch.zeros((4, 4, 3), dtype=torch.float32),
            torch.ones((4, 4, 3), dtype=torch.float32),
        ],
    )

    assert captured["path"] == "/images/edits"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert set(payload) == {
        "model",
        "prompt",
        "size",
        "quality",
        "output_format",
        "response_format",
        "images",
    }
    assert payload["model"] == "gpt-image-2"
    assert payload["prompt"] == "edit"
    assert payload["size"] == "1024x1024"
    assert payload["quality"] == "high"
    assert payload["output_format"] == "png"
    assert payload["response_format"] == "b64_json"
    assert len(payload["images"]) == 2
    assert payload["images"][0]["image_url"].startswith("data:image/jpeg;base64,")
    assert len(results) == 1


def test_image2_reference_data_url_downscales_large_images() -> None:
    large_image = torch.zeros((1800, 2400, 3), dtype=torch.float32)

    data_url = Image2Client._to_data_url(large_image)
    decoded = base64_to_pil_image(data_url)

    assert data_url.startswith("data:image/jpeg;base64,")
    assert max(decoded.size) <= 1536


def test_image2_generate_builds_minimal_documented_payload(monkeypatch) -> None:
    client = Image2Client("image-key")
    captured: dict[str, object] = {}

    def fake_json_request(path, payload, stage, node_name, model):
        captured["path"] = path
        captured["payload"] = payload
        encoded = pil_image_to_base64(Image.new("RGB", (4, 4), (255, 255, 255)))
        return {"data": [{"b64_json": encoded}]}

    monkeypatch.setattr(client, "_json_request", fake_json_request)

    client.generate(
        node_name="Nanaix_Text",
        prompt="hello",
        model="gpt-image-2",
        size="1024x1024",
        n=1,
        quality="high",
        output_format="png",
        background="transparent",
        style="vivid",
        moderation="auto",
        output_compression=45,
        partial_images=3,
        stream=False,
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert captured["path"] == "/images/generations"
    assert payload == {
        "model": "gpt-image-2",
        "prompt": "hello",
        "size": "1024x1024",
        "quality": "high",
        "output_format": "png",
        "response_format": "b64_json",
    }


def test_image2_generate_ignores_unstable_stream_options(monkeypatch) -> None:
    client = Image2Client("image-key")
    captured: dict[str, object] = {}

    def fake_json_request(path, payload, stage, node_name, model):
        captured["path"] = path
        captured["payload"] = payload
        encoded = pil_image_to_base64(Image.new("RGB", (4, 4), (10, 20, 30)))
        return {"data": [{"b64_json": encoded}]}

    monkeypatch.setattr(client, "_json_request", fake_json_request)

    tensors = client.generate(
        node_name="Nanaix_Text",
        prompt="hello",
        model="gpt-image-2",
        size="1024x1024",
        n=1,
        quality="high",
        output_format="png",
        background="auto",
        style="natural",
        moderation="auto",
        output_compression=0,
        partial_images=2,
        stream=True,
    )

    assert len(tensors) == 1
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert "stream" not in payload
    assert "partial_images" not in payload
    assert captured["path"] == "/images/generations"


def test_image2_edit_ignores_unstable_stream_options(monkeypatch) -> None:
    client = Image2Client("image-key")
    captured: dict[str, object] = {}

    def fake_json_request(path, payload, stage, node_name, model):
        captured["path"] = path
        captured["payload"] = payload
        encoded = payload["images"][0]["image_url"].split(",", 1)[1]
        return {"data": [{"b64_json": encoded}]}

    monkeypatch.setattr(client, "_json_request", fake_json_request)

    tensors = client.edit(
        node_name="Nanaix_Image",
        prompt="hello",
        model="gpt-image-2",
        size="1024x1024",
        n=1,
        quality="high",
        output_format="png",
        background="auto",
        style="natural",
        moderation="auto",
        output_compression=0,
        partial_images=3,
        stream=True,
        reference_images=[torch.zeros((4, 4, 3), dtype=torch.float32)],
    )

    assert len(tensors) == 1
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert "stream" not in payload
    assert "partial_images" not in payload
    assert captured["path"] == "/images/edits"


def test_image2_stream_request_reads_completed_event() -> None:
    client = Image2Client("image-key")
    encoded = pil_image_to_base64(Image.new("RGB", (4, 4), (255, 255, 255)))
    body = (
        'event: image_generation.partial_image\n'
        'data: {"data":[{"b64_json":"ignored"}]}\n\n'
        'event: image_generation.completed\n'
        f'data: {{"data":[{{"b64_json":"{encoded}"}}]}}\n\n'
    ).encode("utf-8")

    payload = client._stream_request(
        "/images/generations",
        {"model": "gpt-image-2", "stream": True},
        stage="generation stream",
        node_name="Nanaix_Text",
        model="gpt-image-2",
        raw_response=body,
    )

    assert payload["data"][0]["b64_json"] == encoded


def test_image2_stream_request_reports_seen_event_names_when_completed_is_missing() -> None:
    body = (
        'event: image_generation.partial_image\n'
        'data: {"progress": 0.5}\n\n'
        'event: image_generation.keepalive\n'
        'data: {"ts": 1}\n\n'
    ).encode("utf-8")

    with pytest.raises(NanaixNodeError) as error:
        Image2Client._parse_sse_payload(
            body,
            stage="generation stream",
            node_name="Nanaix_Text",
        )

    text = str(error.value)
    assert "stream completed without a final image payload" in text
    assert "image_generation.partial_image" in text
    assert "image_generation.keepalive" in text
    assert '{"progress": 0.5}' in text


def test_image2_raw_request_normalizes_http_error(monkeypatch) -> None:
    client = Image2Client("bad-key")

    def fake_urlopen(_request, timeout=0):
        raise HTTPError(
            url="https://api.nanaix.com/v1/images/generations",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=FakeResponse(b'{"error":"Invalid API key"}'),
        )

    monkeypatch.setattr("services.image2_client.request.urlopen", fake_urlopen)

    with pytest.raises(NanaixNodeError) as error:
        client._raw_request(
            "/images/generations",
            b"{}",
            {"Authorization": "Bearer bad-key"},
            stage="generation request",
            node_name="Nanaix_Text",
        )

    assert "Invalid API key" in str(error.value) or "Authorization header" in str(error.value)


def test_image2_raw_request_parses_structured_error_payload(monkeypatch) -> None:
    client = Image2Client("bad-key")

    def fake_urlopen(_request, timeout=0):
        raise HTTPError(
            url="https://api.nanaix.com/v1/images/generations",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=FakeResponse(b'{"error":{"message":"Images API is not supported for this platform"}}'),
        )

    monkeypatch.setattr("services.image2_client.request.urlopen", fake_urlopen)

    with pytest.raises(NanaixNodeError) as error:
        client._raw_request(
            "/images/generations",
            b"{}",
            {"Authorization": "Bearer bad-key"},
            stage="generation request",
            node_name="Nanaix_Text",
        )

    assert "HTTP 404" in str(error.value)
    assert "image-enabled platform group" in str(error.value)


def test_image2_raw_request_uses_extended_generation_timeout(monkeypatch) -> None:
    client = Image2Client("image-key")
    captured: dict[str, object] = {}

    def fake_urlopen(_request, **kwargs):
        captured["kwargs"] = kwargs
        encoded = pil_image_to_base64(Image.new("RGB", (4, 4), (255, 255, 255)))
        return FakeResponse(json.dumps({"data": [{"b64_json": encoded}]}).encode("utf-8"))

    monkeypatch.setattr("services.image2_client.request.urlopen", fake_urlopen)

    payload = client._raw_request(
        "/images/edits",
        b"{}",
        {"Authorization": "Bearer image-key"},
        stage="edit request",
        node_name="Nanaix_Image",
        model="gpt-image-2",
    )

    assert payload["data"]
    assert captured["kwargs"]["timeout"] == 600


def test_banana_status_to_tensors_requires_urls() -> None:
    with pytest.raises(NanaixNodeError) as error:
        BananaClient._status_to_tensors({"results": []}, node_name="Nanaix_Text", model="nano-banana-2")

    assert "completed without any downloadable image results" in str(error.value)


def test_banana_status_to_tensors_supports_data_urls() -> None:
    image = Image.new("RGB", (4, 4), (255, 0, 0))
    encoded = pil_image_to_base64(image)

    tensors = BananaClient._status_to_tensors(
        {"results": [{"url": f"data:image/png;base64,{encoded}"}]},
        node_name="Nanaix_Text",
        model="nano-banana-2",
    )

    assert len(tensors) == 1
    assert tensors[0].shape == (4, 4, 3)


def test_banana_status_to_tensors_supports_b64_json() -> None:
    image = Image.new("RGB", (4, 4), (255, 0, 0))
    encoded = pil_image_to_base64(image)

    tensors = BananaClient._status_to_tensors(
        {"results": [{"b64_json": encoded}]},
        node_name="Nanaix_Image",
        model="nano-banana-2",
    )

    assert len(tensors) == 1
    assert tensors[0].shape == (4, 4, 3)


def test_banana_reference_data_url_downscales_large_images() -> None:
    large_image = torch.zeros((1800, 2400, 3), dtype=torch.float32)

    data_url = BananaClient._to_data_url(large_image)
    decoded = base64_to_pil_image(data_url)

    assert data_url.startswith("data:image/jpeg;base64,")
    assert max(decoded.size) <= 1536


def test_banana_post_generate_wraps_timeout_with_actionable_message(monkeypatch) -> None:
    client = BananaClient("banana-key")
    captured: dict[str, object] = {}

    def fake_urlopen(_request, timeout=0):
        captured["timeout"] = timeout
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr("services.banana_client.request.urlopen", fake_urlopen)

    with pytest.raises(NanaixNodeError) as error:
        client._post_generate({"model": "nano-banana-2", "prompt": "edit", "images": ["data:image/jpeg;base64,AA=="]}, "Nanaix_Image")

    text = str(error.value)
    assert captured["timeout"] == 300
    assert "timed out while waiting for Nanaix" in text
    assert "fewer or smaller reference images" in text


def test_banana_result_polling_wraps_timeout(monkeypatch) -> None:
    client = BananaClient("banana-key")

    def fake_urlopen(_request, timeout=0):
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr("services.banana_client.request.urlopen", fake_urlopen)

    with pytest.raises(NanaixNodeError) as error:
        client._fetch_result("task-1", node_name="Nanaix_Image", model="nano-banana-pro")

    assert "result polling" in str(error.value)
    assert "timed out while waiting for Nanaix" in str(error.value)


def test_banana_result_download_wraps_timeout(monkeypatch) -> None:
    def fake_load_url_image(url, timeout=0):
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr("services.banana_client.load_url_image", fake_load_url_image)

    with pytest.raises(NanaixNodeError) as error:
        BananaClient._status_to_tensors(
            {"results": [{"url": "https://example.com/generated.png"}]},
            node_name="Nanaix_Image",
            model="nano-banana-2",
        )

    assert "downloading result image" in str(error.value)
    assert "timed out while waiting for Nanaix image URL" in str(error.value)


def test_banana_generate_polls_once_per_requested_image(monkeypatch) -> None:
    client = BananaClient("banana-key", timeout_seconds=1, poll_interval_seconds=0)
    submitted_payloads: list[dict[str, object]] = []
    polled_ids: list[str] = []

    def fake_post_generate(payload, node_name):
        submitted_payloads.append(payload)
        return {"id": f"task-{len(submitted_payloads)}"}

    def fake_wait_for_results(task_id, node_name, model):
        polled_ids.append(task_id)
        return [torch.zeros((4, 4, 3), dtype=torch.float32)]

    monkeypatch.setattr(client, "_post_generate", fake_post_generate)
    monkeypatch.setattr(client, "_wait_for_results", fake_wait_for_results)

    results = client.generate(
        node_name="Nanaix_Text",
        prompt="hello",
        model="nano-banana-pro",
        aspect_ratio="1:1",
        image_size="2K",
        n=2,
        quality="high",
        output_format="png",
    )

    assert len(results) == 2
    assert len(submitted_payloads) == 2
    assert polled_ids == ["task-1", "task-2"]
    assert submitted_payloads[0] == {
        "model": "nano-banana-pro",
        "prompt": "hello",
    }


def test_banana_wait_for_results_accepts_lowercase_succeeded(monkeypatch) -> None:
    client = BananaClient("banana-key", timeout_seconds=1, poll_interval_seconds=0)
    encoded = pil_image_to_base64(Image.new("RGB", (4, 4), (0, 0, 255)))

    monkeypatch.setattr(
        client,
        "_fetch_result",
        lambda task_id, node_name, model: {
            "status": "succeeded",
            "results": [{"b64_json": encoded}],
        },
    )

    results = client._wait_for_results("task-1", node_name="Nanaix_Image", model="nano-banana-2")

    assert len(results) == 1
    assert results[0].shape == (4, 4, 3)


def test_banana_generate_sends_reference_images_without_unstable_size_options(monkeypatch) -> None:
    client = BananaClient("banana-key", timeout_seconds=1, poll_interval_seconds=0)
    submitted_payloads: list[dict[str, object]] = []

    def fake_post_generate(payload, node_name):
        submitted_payloads.append(payload)
        return {"id": "task-1"}

    monkeypatch.setattr(client, "_post_generate", fake_post_generate)
    monkeypatch.setattr(client, "_wait_for_results", lambda task_id, node_name, model: [torch.zeros((4, 4, 3), dtype=torch.float32)])

    client.generate(
        node_name="Nanaix_Image",
        prompt="edit",
        model="nano-banana-2",
        aspect_ratio="1:1",
        image_size="2K",
        n=1,
        quality="high",
        output_format="png",
        reference_images=[torch.zeros((4, 4, 3), dtype=torch.float32)],
    )

    assert len(submitted_payloads) == 1
    payload = submitted_payloads[0]
    assert payload["model"] == "nano-banana-2"
    assert payload["prompt"] == "edit"
    assert isinstance(payload["images"], list)
    assert "aspectRatio" not in payload
    assert "imageSize" not in payload
    assert "replyType" not in payload


def test_banana_generate_returns_immediate_completed_results(monkeypatch) -> None:
    client = BananaClient("banana-key", timeout_seconds=1, poll_interval_seconds=0)
    image = Image.new("RGB", (4, 4), (0, 255, 0))
    encoded = pil_image_to_base64(image)

    monkeypatch.setattr(
        client,
        "_post_generate",
        lambda payload, node_name: {
            "status": "COMPLETED",
            "results": [{"url": f"data:image/png;base64,{encoded}"}],
        },
    )

    results = client.generate(
        node_name="Nanaix_Text",
        prompt="hello",
        model="nano-banana-pro",
        aspect_ratio="1:1",
        image_size="2K",
        n=1,
        quality="high",
        output_format="png",
    )

    assert len(results) == 1
    assert results[0].shape == (4, 4, 3)


def test_banana_generate_returns_immediate_succeeded_results(monkeypatch) -> None:
    client = BananaClient("banana-key", timeout_seconds=1, poll_interval_seconds=0)
    image = Image.new("RGB", (4, 4), (0, 255, 0))
    encoded = pil_image_to_base64(image)

    monkeypatch.setattr(
        client,
        "_post_generate",
        lambda payload, node_name: {
            "status": "succeeded",
            "results": [{"b64_json": encoded}],
        },
    )

    results = client.generate(
        node_name="Nanaix_Image",
        prompt="hello",
        model="nano-banana-2",
        aspect_ratio="1:1",
        image_size="2K",
        n=1,
        quality="high",
        output_format="png",
    )

    assert len(results) == 1
    assert results[0].shape == (4, 4, 3)


def test_banana_wait_for_results_surfaces_upstream_failure_detail(monkeypatch) -> None:
    client = BananaClient("banana-key", timeout_seconds=1, poll_interval_seconds=0)

    monkeypatch.setattr(
        client,
        "_fetch_result",
        lambda task_id, node_name, model: {
            "status": "FAILED",
            "error": {"message": "No available compatible accounts"},
        },
    )

    with pytest.raises(NanaixNodeError) as error:
        client._wait_for_results("task-123", node_name="Nanaix_Text", model="nano-banana-pro")

    text = str(error.value)
    assert "task task-123 failed with status FAILED" in text
    assert "No available upstream image accounts are currently compatible." in text
