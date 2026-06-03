from __future__ import annotations

import json
from urllib import request
from urllib.error import HTTPError, URLError

try:
    from ..utils.errors import NanaixNodeError, normalize_api_error
    from ..utils.image_io import base64_to_pil_image, pil_image_to_data_url, pil_image_to_tensor, tensor_image_to_pil
except ImportError:  # pragma: no cover - local pytest import fallback
    from utils.errors import NanaixNodeError, normalize_api_error
    from utils.image_io import base64_to_pil_image, pil_image_to_data_url, pil_image_to_tensor, tensor_image_to_pil


class Image2Client:
    BASE_URL = "https://api.nanaix.com/v1"
    REQUEST_TIMEOUT_SECONDS = 600
    REFERENCE_UPLOAD_MAX_EDGE = 1536

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def generate(
        self,
        *,
        node_name: str,
        prompt: str,
        model: str,
        size: str,
        n: int,
        quality: str,
        output_format: str,
        background: str,
        style: str,
        moderation: str,
        output_compression: int,
        partial_images: int,
        stream: bool,
    ) -> list[object]:
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "output_format": output_format,
            "response_format": "b64_json",
        }
        data = self._json_request("/images/generations", payload, stage="generation request", node_name=node_name, model=model)
        return self._response_to_tensors(data, stage="generation decode", node_name=node_name, model=model)

    def list_models(self, *, node_name: str) -> list[str]:
        payload = self._get_request("/models", stage="model list request", node_name=node_name)
        data_items = payload.get("data", [])
        models = []
        if isinstance(data_items, list):
            for item in data_items:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    models.append(item["id"])
        return models

    def edit(
        self,
        *,
        node_name: str,
        prompt: str,
        model: str,
        size: str,
        n: int,
        quality: str,
        output_format: str,
        background: str,
        style: str,
        moderation: str,
        output_compression: int,
        partial_images: int,
        stream: bool,
        reference_images: list,
    ) -> list[object]:
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "output_format": output_format,
            "response_format": "b64_json",
            "images": [{"image_url": self._to_data_url(tensor)} for tensor in reference_images],
        }
        data = self._json_request("/images/edits", payload, stage="edit request", node_name=node_name, model=model)
        return self._response_to_tensors(data, stage="edit decode", node_name=node_name, model=model)

    def _json_request(self, path: str, payload: dict[str, object], stage: str, node_name: str, model: str) -> dict[str, object]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = json.dumps(payload).encode("utf-8")
        return self._raw_request(path, data, headers, stage, node_name, model)

    def _get_request(self, path: str, stage: str, node_name: str) -> dict[str, object]:
        req = request.Request(
            f"{self.BASE_URL}{path}",
            headers={"Authorization": f"Bearer {self.api_key}"},
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise normalize_api_error(
                node_name,
                "gpt-image-2",
                f"{stage} (HTTP {error.code})",
                detail,
            ) from error
        except URLError as error:
            raise NanaixNodeError(f"{node_name}: gpt-image-2 failed during {stage}: {error.reason}") from error
        except TimeoutError as error:
            raise NanaixNodeError(f"{node_name}: gpt-image-2 failed during {stage}: request timed out while waiting for Nanaix.") from error

    def _raw_request(
        self,
        path: str,
        data: bytes,
        headers: dict[str, str],
        stage: str,
        node_name: str,
        model: str = "gpt-image-2",
    ) -> dict[str, object]:
        req = request.Request(f"{self.BASE_URL}{path}", data=data, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self.REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise normalize_api_error(
                node_name,
                model,
                f"{stage} (HTTP {error.code})",
                detail,
            ) from error
        except URLError as error:
            raise NanaixNodeError(f"{node_name}: {model} failed during {stage}: {error.reason}") from error
        except TimeoutError as error:
            raise NanaixNodeError(
                f"{node_name}: {model} failed during {stage}: request timed out while waiting for Nanaix. "
                "For image edits, try fewer or smaller reference images, or a smaller output size."
            ) from error

    def _stream_request(
        self,
        path: str,
        payload: dict[str, object],
        stage: str,
        node_name: str,
        model: str,
        raw_response: bytes | None = None,
    ) -> dict[str, object]:
        if raw_response is None:
            req = request.Request(
                f"{self.BASE_URL}{path}",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                },
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self.REQUEST_TIMEOUT_SECONDS) as response:
                    raw_response = response.read()
            except HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")
                raise normalize_api_error(
                    node_name,
                    model,
                    f"{stage} (HTTP {error.code})",
                    detail,
                ) from error
            except URLError as error:
                raise NanaixNodeError(f"{node_name}: {model} failed during {stage}: {error.reason}") from error
            except TimeoutError as error:
                raise NanaixNodeError(
                    f"{node_name}: {model} failed during {stage}: request timed out while waiting for Nanaix. "
                    "For image edits, try fewer or smaller reference images, or a smaller output size."
                ) from error

        return self._parse_sse_payload(raw_response, stage=stage, node_name=node_name, model=model)

    @staticmethod
    def _parse_sse_payload(raw_response: bytes, *, stage: str, node_name: str, model: str = "gpt-image-2") -> dict[str, object]:
        text = raw_response.decode("utf-8", errors="replace")
        completed_payload: dict[str, object] | None = None
        seen_events: list[str] = []
        data_previews: list[str] = []
        blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
        for block in blocks:
            event_name = ""
            data_lines: list[str] = []
            for line in block.splitlines():
                if line.startswith("event:"):
                    event_name = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data_lines.append(line.split(":", 1)[1].strip())
            if event_name:
                seen_events.append(event_name)
            if data_lines:
                data_previews.append("\n".join(data_lines))
            if not data_lines:
                continue
            try:
                payload = json.loads("\n".join(data_lines))
            except json.JSONDecodeError:
                continue
            if event_name.endswith(".completed") and isinstance(payload, dict):
                completed_payload = payload
        if completed_payload is None:
            if seen_events:
                event_summary = ", ".join(seen_events[:4])
                if len(seen_events) > 4:
                    event_summary = f"{event_summary}, ..."
                preview_suffix = ""
                if data_previews:
                    preview = data_previews[0]
                    if len(preview) > 160:
                        preview = f"{preview[:157]}..."
                    preview_suffix = f" First data: {preview}"
                raise NanaixNodeError(
                    f"{node_name}: {model} failed during {stage}: "
                    f"stream completed without a final image payload. Seen events: {event_summary}.{preview_suffix}"
                )
            raise NanaixNodeError(f"{node_name}: {model} failed during {stage}: stream completed without a final image payload")
        return completed_payload

    @staticmethod
    def _response_to_tensors(payload: dict[str, object], stage: str, node_name: str, model: str = "gpt-image-2") -> list[object]:
        tensors = []
        data_items = payload.get("data", [])
        if not isinstance(data_items, list) or not data_items:
            raise NanaixNodeError(f"{node_name}: {model} failed during {stage}: no images were returned")
        for item in data_items:
            if isinstance(item, dict):
                encoded = item.get("b64_json") or item.get("url")
                if not isinstance(encoded, str):
                    continue
                tensors.append(pil_image_to_tensor(base64_to_pil_image(encoded)))
        if not tensors:
            raise NanaixNodeError(
                f"{node_name}: {model} failed during {stage}: response did not contain decodable images"
            )
        return tensors

    @staticmethod
    def _to_data_url(image_tensor) -> str:
        image = tensor_image_to_pil(image_tensor)
        return pil_image_to_data_url(image, output_format="JPEG", max_edge=Image2Client.REFERENCE_UPLOAD_MAX_EDGE, quality=85)
