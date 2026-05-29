from __future__ import annotations

import json
import time
from urllib import parse, request
from urllib.error import HTTPError, URLError

try:
    from ..utils.errors import NanaixNodeError, normalize_api_error
    from ..utils.image_io import base64_to_pil_image, load_url_image, pil_image_to_data_url, pil_image_to_tensor, tensor_image_to_pil
except ImportError:  # pragma: no cover - local pytest import fallback
    from utils.errors import NanaixNodeError, normalize_api_error
    from utils.image_io import base64_to_pil_image, load_url_image, pil_image_to_data_url, pil_image_to_tensor, tensor_image_to_pil


class BananaClient:
    BASE_URL = "https://api.nanaix.com/v1"
    SUPPORTED_MODELS = ["nano-banana-2", "nano-banana-pro"]
    SUCCESS_STATUSES = {"COMPLETED", "SUCCEEDED", "SUCCESS", "DONE", "FINISHED"}
    FAILURE_STATUSES = {"FAILED", "ERROR", "CANCELLED", "CANCELED"}
    REQUEST_TIMEOUT_SECONDS = 300
    RESULT_DOWNLOAD_TIMEOUT_SECONDS = 120
    REFERENCE_UPLOAD_MAX_EDGE = 1536

    def __init__(self, api_key: str, timeout_seconds: int = 120, poll_interval_seconds: float = 2.0) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds

    def generate(
        self,
        *,
        node_name: str,
        prompt: str,
        model: str,
        aspect_ratio: str,
        image_size: str,
        n: int,
        quality: str,
        output_format: str,
        reference_images: list | None = None,
    ) -> list[object]:
        payload = {
            "model": model,
            "prompt": prompt,
        }
        if reference_images:
            payload["images"] = [self._to_data_url(image) for image in reference_images]

        results = []
        for _ in range(n):
            task = self._post_generate(payload, node_name=node_name)
            if self._is_success_status(task.get("status")):
                results.extend(self._status_to_tensors(task, node_name=node_name, model=model))
                continue

            task_id = task.get("id")
            if not isinstance(task_id, str) or not task_id:
                raise NanaixNodeError(f"{node_name}: {model} did not return a task id or completed results")
            results.extend(self._wait_for_results(task_id, node_name=node_name, model=model))
        return results

    def list_models(self, *, node_name: str) -> list[str]:
        return list(self.SUPPORTED_MODELS)

    def _post_generate(self, payload: dict[str, object], node_name: str) -> dict[str, object]:
        req = request.Request(
            f"{self.BASE_URL}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise normalize_api_error(
                node_name,
                str(payload.get("model", "banana")),
                f"generate request (HTTP {error.code})",
                detail,
            ) from error
        except URLError as error:
            raise NanaixNodeError(
                f"{node_name}: {payload.get('model', 'banana')} failed during generate request: {error.reason}"
            ) from error
        except TimeoutError as error:
            raise NanaixNodeError(
                f"{node_name}: {payload.get('model', 'banana')} failed during generate request: "
                "request timed out while waiting for Nanaix. For image edits, try fewer or smaller reference images."
            ) from error

    def _wait_for_results(self, task_id: str, node_name: str, model: str) -> list[object]:
        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            status = self._fetch_result(task_id, node_name=node_name, model=model)
            state = status.get("status")
            if self._is_success_status(state):
                return self._status_to_tensors(status, node_name=node_name, model=model)
            if self._is_failure_status(state):
                detail = self._extract_failure_detail(status)
                message = f"{node_name}: {model} task {task_id} failed with status {state}"
                if detail:
                    normalized = normalize_api_error(node_name, model, f"task {task_id} failure detail", detail)
                    raise NanaixNodeError(f"{message}: {normalized.message}") from None
                raise NanaixNodeError(message)
            time.sleep(self.poll_interval_seconds)
        raise NanaixNodeError(f"{node_name}: {model} task {task_id} timed out waiting for task completion")

    def _fetch_result(self, task_id: str, node_name: str, model: str) -> dict[str, object]:
        url = f"{self.BASE_URL}/api/result?{parse.urlencode({'id': task_id})}"
        req = request.Request(url, headers={"Authorization": f"Bearer {self.api_key}"}, method="GET")
        try:
            with request.urlopen(req, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise normalize_api_error(node_name, model, f"result polling (HTTP {error.code})", detail) from error
        except URLError as error:
            raise NanaixNodeError(f"{node_name}: {model} failed during result polling: {error.reason}") from error
        except TimeoutError as error:
            raise NanaixNodeError(
                f"{node_name}: {model} failed during result polling: request timed out while waiting for Nanaix."
            ) from error

    @staticmethod
    def _status_to_tensors(payload: dict[str, object], node_name: str, model: str) -> list[object]:
        results = payload.get("results", [])
        tensors = []
        if isinstance(results, list):
            for item in results:
                if not isinstance(item, dict):
                    continue
                encoded = item.get("b64_json")
                if isinstance(encoded, str):
                    tensors.append(pil_image_to_tensor(base64_to_pil_image(encoded)))
                    continue
                url = item.get("url")
                if not isinstance(url, str):
                    continue
                if url.startswith("data:image/"):
                    tensors.append(pil_image_to_tensor(base64_to_pil_image(url)))
                else:
                    try:
                        image = load_url_image(url, timeout=BananaClient.RESULT_DOWNLOAD_TIMEOUT_SECONDS)
                    except TimeoutError as error:
                        raise NanaixNodeError(
                            f"{node_name}: {model} failed while downloading result image: "
                            "request timed out while waiting for Nanaix image URL."
                        ) from error
                    tensors.append(pil_image_to_tensor(image))
        if not tensors:
            raise NanaixNodeError(f"{node_name}: {model} completed without any downloadable image results")
        return tensors

    @staticmethod
    def _extract_failure_detail(payload: dict[str, object]) -> str:
        error = payload.get("error")
        if isinstance(error, dict):
            for key in ("message", "detail", "error"):
                value = error.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        elif isinstance(error, str) and error.strip():
            return error

        for key in ("message", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return ""

    @classmethod
    def _is_success_status(cls, status: object) -> bool:
        return isinstance(status, str) and status.strip().upper() in cls.SUCCESS_STATUSES

    @classmethod
    def _is_failure_status(cls, status: object) -> bool:
        return isinstance(status, str) and status.strip().upper() in cls.FAILURE_STATUSES

    @staticmethod
    def _to_data_url(image_tensor) -> str:
        image = tensor_image_to_pil(image_tensor)
        return pil_image_to_data_url(image, output_format="JPEG", max_edge=BananaClient.REFERENCE_UPLOAD_MAX_EDGE, quality=85)
