from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image
import pytest

from scripts import smoke_test


class RecordingImage2Client:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.received_api_key = api_key
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(("generate", kwargs))
        return [
            smoke_test.pil_image_to_tensor(Image.new("RGB", (4, 4), (255, 0, 0))),
            smoke_test.pil_image_to_tensor(Image.new("RGB", (4, 4), (255, 255, 0))),
        ]

    def list_models(self, **kwargs):
        self.calls.append(("list_models", kwargs))
        return ["gpt-image-2", "gpt-image-3"]

    def edit(self, **kwargs):
        self.calls.append(("edit", kwargs))
        return [smoke_test.pil_image_to_tensor(Image.new("RGB", (4, 4), (0, 255, 0)))]


class RecordingBananaClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.received_api_key = api_key
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return [smoke_test.pil_image_to_tensor(Image.new("RGB", (4, 4), (0, 0, 255)))]

    def list_models(self, **kwargs):
        self.calls.append(("list_models", kwargs))
        return ["nano-banana-2", "nano-banana-pro"]


def test_smoke_test_uses_image2_generate(monkeypatch, tmp_path: Path) -> None:
    image2_client = RecordingImage2Client("image-key")
    monkeypatch.setattr(smoke_test, "Image2Client", lambda key: image2_client)

    output_path = tmp_path / "output.png"
    monkeypatch.setattr(
        "sys.argv",
        [
            "smoke_test.py",
            "--model",
            "gpt-image-2",
            "--prompt",
            "hello",
            "--image2-key",
            "image-key",
            "--output",
            str(output_path),
        ],
    )

    exit_code = smoke_test.main()

    assert exit_code == 0
    assert not output_path.exists()
    assert (tmp_path / "output_1.png").exists()
    assert (tmp_path / "output_2.png").exists()
    assert image2_client.calls[0][0] == "generate"
    assert image2_client.calls[0][1]["model"] == "gpt-image-2"


def test_smoke_test_uses_banana_edit_with_reference_images(monkeypatch, tmp_path: Path) -> None:
    banana_client = RecordingBananaClient("banana-key")
    monkeypatch.setattr(smoke_test, "BananaClient", lambda key: banana_client)

    reference_path = tmp_path / "reference.png"
    Image.new("RGB", (4, 4), (123, 123, 123)).save(reference_path)
    output_path = tmp_path / "output.png"
    monkeypatch.setattr(
        "sys.argv",
        [
            "smoke_test.py",
            "--model",
            "nano-banana-pro",
            "--prompt",
            "hello",
            "--banana-key",
            "banana-key",
            "--reference-image",
            str(reference_path),
            "--output",
            str(output_path),
        ],
    )

    exit_code = smoke_test.main()

    assert exit_code == 0
    assert output_path.exists()
    assert len(banana_client.calls[0]["reference_images"]) == 1


def test_smoke_test_warns_when_banana_ignores_image2_only_options(monkeypatch, tmp_path: Path) -> None:
    banana_client = RecordingBananaClient("banana-key")
    monkeypatch.setattr(smoke_test, "BananaClient", lambda key: banana_client)
    output_path = tmp_path / "output.png"
    monkeypatch.setattr(
        "sys.argv",
        [
            "smoke_test.py",
            "--model",
            "nano-banana-pro",
            "--prompt",
            "hello",
            "--banana-key",
            "banana-key",
            "--output",
            str(output_path),
            "--background",
            "transparent",
            "--style",
            "vivid",
            "--moderation",
            "low",
            "--output-compression",
            "20",
            "--partial-images",
            "2",
            "--stream",
        ],
    )

    with pytest.warns(UserWarning, match="ignored for nano-banana-pro"):
        exit_code = smoke_test.main()

    assert exit_code == 0
    assert output_path.exists()


def test_smoke_test_supports_list_models(monkeypatch, capsys) -> None:
    image2_client = RecordingImage2Client("image-key")
    monkeypatch.setattr(smoke_test, "Image2Client", lambda key: image2_client)
    monkeypatch.setattr(
        "sys.argv",
        [
            "smoke_test.py",
            "--model",
            "gpt-image-2",
            "--image2-key",
            "image-key",
            "--list-models",
        ],
    )

    exit_code = smoke_test.main()

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "gpt-image-2" in output
    assert image2_client.calls[0][0] == "list_models"


def test_smoke_test_supports_banana_list_models(monkeypatch, capsys) -> None:
    banana_client = RecordingBananaClient("banana-key")
    monkeypatch.setattr(smoke_test, "BananaClient", lambda key: banana_client)
    monkeypatch.setattr(
        "sys.argv",
        [
            "smoke_test.py",
            "--model",
            "nano-banana-pro",
            "--banana-key",
            "banana-key",
            "--list-models",
        ],
    )

    exit_code = smoke_test.main()

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "nano-banana-pro" in output
    assert banana_client.calls[0][0] == "list_models"


def test_smoke_test_preflight_reports_image2_visibility(monkeypatch, capsys) -> None:
    image2_client = RecordingImage2Client("image-key")
    monkeypatch.setattr(smoke_test, "Image2Client", lambda key: image2_client)
    monkeypatch.setattr(
        smoke_test,
        "parse_args",
        lambda: argparse.Namespace(
            model="gpt-image-2",
            prompt="",
            width=1024,
            height=1024,
            n=1,
            quality="high",
            output_format="png",
            background="auto",
            style="natural",
            moderation="auto",
            output_compression=0,
            partial_images=0,
            stream=False,
            output="",
            image2_key="image-key",
            banana_key="",
            list_models=False,
            preflight=True,
            reference_image=[],
        ),
    )

    exit_code = smoke_test.main()

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "image-2: OK - visible models: gpt-image-2, gpt-image-3" in output
    assert image2_client.calls[0][0] == "list_models"


def test_smoke_test_preflight_requires_matching_key(monkeypatch) -> None:
    monkeypatch.setattr(
        smoke_test,
        "parse_args",
        lambda: argparse.Namespace(
            model="nano-banana-pro",
            prompt="",
            width=1024,
            height=1024,
            n=1,
            quality="high",
            output_format="png",
            background="auto",
            style="natural",
            moderation="auto",
            output_compression=0,
            partial_images=0,
            stream=False,
            output="",
            image2_key="",
            banana_key="",
            list_models=False,
            preflight=True,
            reference_image=[],
        ),
    )

    with pytest.raises(ValueError, match="--banana-key is required"):
        smoke_test.main()


def test_smoke_test_passes_runtime_options(monkeypatch, tmp_path: Path) -> None:
    image2_client = RecordingImage2Client("image-key")
    monkeypatch.setattr(smoke_test, "Image2Client", lambda key: image2_client)
    output_path = tmp_path / "output.png"
    monkeypatch.setattr(
        "sys.argv",
        [
            "smoke_test.py",
            "--model",
            "gpt-image-2",
            "--prompt",
            "hello",
            "--image2-key",
            "image-key",
            "--output",
            str(output_path),
            "--n",
            "2",
            "--quality",
            "medium",
            "--output-format",
            "webp",
            "--partial-images",
            "3",
            "--stream",
        ],
    )

    exit_code = smoke_test.main()

    assert exit_code == 0
    assert image2_client.calls[0][1]["n"] == 2
    assert image2_client.calls[0][1]["quality"] == "medium"
    assert image2_client.calls[0][1]["output_format"] == "webp"
    assert image2_client.calls[0][1]["partial_images"] == 3
    assert image2_client.calls[0][1]["stream"] is True


def test_smoke_test_passes_image2_advanced_options_to_generate(monkeypatch, tmp_path: Path) -> None:
    image2_client = RecordingImage2Client("image-key")
    monkeypatch.setattr(smoke_test, "Image2Client", lambda key: image2_client)
    output_path = tmp_path / "output.png"
    monkeypatch.setattr(
        "sys.argv",
        [
            "smoke_test.py",
            "--model",
            "gpt-image-2",
            "--prompt",
            "hello",
            "--image2-key",
            "image-key",
            "--output",
            str(output_path),
            "--background",
            "transparent",
            "--style",
            "vivid",
            "--moderation",
            "low",
            "--output-compression",
            "45",
            "--partial-images",
            "2",
            "--stream",
        ],
    )

    exit_code = smoke_test.main()

    assert exit_code == 0
    assert image2_client.calls[0][0] == "generate"
    assert image2_client.calls[0][1]["model"] == "gpt-image-2"
    assert image2_client.calls[0][1]["background"] == "transparent"
    assert image2_client.calls[0][1]["style"] == "vivid"
    assert image2_client.calls[0][1]["moderation"] == "low"
    assert image2_client.calls[0][1]["output_compression"] == 45
    assert image2_client.calls[0][1]["partial_images"] == 2
    assert image2_client.calls[0][1]["stream"] is True


def test_smoke_test_passes_image2_advanced_options_to_edit(monkeypatch, tmp_path: Path) -> None:
    image2_client = RecordingImage2Client("image-key")
    monkeypatch.setattr(smoke_test, "Image2Client", lambda key: image2_client)

    reference_path = tmp_path / "reference.png"
    Image.new("RGB", (4, 4), (123, 123, 123)).save(reference_path)
    output_path = tmp_path / "output.png"
    monkeypatch.setattr(
        "sys.argv",
        [
            "smoke_test.py",
            "--model",
            "gpt-image-2",
            "--prompt",
            "edit hello",
            "--image2-key",
            "image-key",
            "--reference-image",
            str(reference_path),
            "--output",
            str(output_path),
            "--background",
            "transparent",
            "--style",
            "vivid",
            "--moderation",
            "auto",
            "--output-compression",
            "70",
            "--partial-images",
            "4",
            "--stream",
        ],
    )

    exit_code = smoke_test.main()

    assert exit_code == 0
    assert image2_client.calls[0][0] == "edit"
    assert image2_client.calls[0][1]["model"] == "gpt-image-2"
    assert image2_client.calls[0][1]["background"] == "transparent"
    assert image2_client.calls[0][1]["style"] == "vivid"
    assert image2_client.calls[0][1]["moderation"] == "auto"
    assert image2_client.calls[0][1]["output_compression"] == 70
    assert image2_client.calls[0][1]["partial_images"] == 4
    assert image2_client.calls[0][1]["stream"] is True


def test_smoke_test_does_not_pass_image2_only_options_to_banana(monkeypatch, tmp_path: Path) -> None:
    banana_client = RecordingBananaClient("banana-key")
    monkeypatch.setattr(smoke_test, "BananaClient", lambda key: banana_client)
    output_path = tmp_path / "output.png"
    monkeypatch.setattr(
        "sys.argv",
        [
            "smoke_test.py",
            "--model",
            "nano-banana-pro",
            "--prompt",
            "hello",
            "--banana-key",
            "banana-key",
            "--output",
            str(output_path),
            "--background",
            "transparent",
            "--style",
            "vivid",
            "--moderation",
            "low",
            "--output-compression",
            "45",
            "--partial-images",
            "5",
            "--stream",
        ],
    )

    exit_code = smoke_test.main()

    assert exit_code == 0
    assert "background" not in banana_client.calls[0]
    assert "style" not in banana_client.calls[0]
    assert "moderation" not in banana_client.calls[0]
    assert "output_compression" not in banana_client.calls[0]
    assert "partial_images" not in banana_client.calls[0]
    assert "stream" not in banana_client.calls[0]


def test_smoke_test_requires_prompt_for_generation(monkeypatch) -> None:
    image2_client = RecordingImage2Client("image-key")
    monkeypatch.setattr(smoke_test, "Image2Client", lambda key: image2_client)
    monkeypatch.setattr(
        "sys.argv",
        [
            "smoke_test.py",
            "--model",
            "gpt-image-2",
            "--image2-key",
            "image-key",
            "--output",
            "out.png",
        ],
    )

    try:
        smoke_test.main()
    except ValueError as error:
        assert "--prompt is required" in str(error)
    else:
        raise AssertionError("expected ValueError when prompt is missing for generation")


def test_smoke_test_accepts_image2_key_from_environment(monkeypatch, tmp_path: Path) -> None:
    constructed: dict[str, str] = {}

    def image2_factory(key: str):
        constructed["key"] = key
        return RecordingImage2Client(key)

    monkeypatch.setattr(smoke_test, "Image2Client", image2_factory)
    monkeypatch.setenv(smoke_test.IMAGE2_KEY_ENV, "env-image-key")
    output_path = tmp_path / "output.png"
    monkeypatch.setattr(
        "sys.argv",
        [
            "smoke_test.py",
            "--model",
            "gpt-image-2",
            "--prompt",
            "hello",
            "--output",
            str(output_path),
        ],
    )

    exit_code = smoke_test.main()

    assert exit_code == 0
    assert constructed["key"] == "env-image-key"


def test_smoke_test_accepts_banana_key_from_environment(monkeypatch, tmp_path: Path) -> None:
    constructed: dict[str, str] = {}

    def banana_factory(key: str):
        constructed["key"] = key
        return RecordingBananaClient(key)

    monkeypatch.setattr(smoke_test, "BananaClient", banana_factory)
    monkeypatch.setenv(smoke_test.BANANA_KEY_ENV, "env-banana-key")
    output_path = tmp_path / "output.png"
    monkeypatch.setattr(
        "sys.argv",
        [
            "smoke_test.py",
            "--model",
            "nano-banana-pro",
            "--prompt",
            "hello",
            "--output",
            str(output_path),
        ],
    )

    exit_code = smoke_test.main()

    assert exit_code == 0
    assert constructed["key"] == "env-banana-key"
