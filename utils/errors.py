import json
import warnings
from dataclasses import dataclass


@dataclass
class NanaixNodeError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


KNOWN_ERROR_SNIPPETS = {
    "Invalid API key": "Invalid API key or missing Authorization header.",
    "Images API is not supported for this platform": "This key does not belong to an image-enabled platform group.",
    "No available compatible accounts": "No available upstream image accounts are currently compatible.",
    "image file is required": "The edit request is missing a required source image.",
    "images[].image_url is required": "The edit request is missing a required image URL payload.",
}


def extract_error_detail(detail: str) -> str:
    normalized = detail
    try:
        parsed = json.loads(detail)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        error_value = parsed.get("error")
        if isinstance(error_value, dict) and isinstance(error_value.get("message"), str):
            normalized = error_value["message"]
        elif isinstance(error_value, str):
            normalized = error_value

    for snippet, friendly in KNOWN_ERROR_SNIPPETS.items():
        if snippet in normalized:
            normalized = friendly
            break
    return normalized


def normalize_api_error(node_name: str, model: str, stage: str, detail: str) -> NanaixNodeError:
    normalized = extract_error_detail(detail)
    return NanaixNodeError(f"{node_name}: {model} failed during {stage}: {normalized}")


def prompt_required_message(node_name: str) -> str:
    if node_name == "Nanaix_Image":
        return "prompt is required. Describe how Nanaix should change the reference image."
    return "prompt is required. Describe the image you want Nanaix to generate."


def required_key_message(model: str, field_name: str = "api_key") -> str:
    provider_label = "image-2" if model.startswith("gpt-image-") else "nano-banana"
    return (
        f"{model} requires {field_name}. Paste your {provider_label} key into the node. "
        "Saved config only pre-fills new nodes; a blank visible key is still treated as missing."
    )


def reference_image_required_message() -> str:
    return "At least one reference image is required. Connect image_1 or another IMAGE input before queueing Nanaix_Image."


def warn_ignored_image2_only_options(
    *,
    model: str,
    background: str,
    style: str,
    moderation: str,
    output_compression: int,
    partial_images: int,
    stream: bool,
) -> None:
    ignored: list[str] = []
    if background != "auto":
        ignored.append(f"background={background}")
    if style != "natural":
        ignored.append(f"style={style}")
    if moderation != "auto":
        ignored.append(f"moderation={moderation}")
    if output_compression != 0:
        ignored.append(f"output_compression={output_compression}")
    if partial_images != 0:
        ignored.append(f"partial_images={partial_images}")
    if stream:
        ignored.append("stream=true")
    if ignored:
        warnings.warn(
            f"The following gpt-image-2-only options are ignored for {model}: {', '.join(ignored)}.",
            UserWarning,
            stacklevel=2,
        )
