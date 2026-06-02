from __future__ import annotations

ROUTER_INPUT_KEYS = (
    "prompt",
    "model",
    "width",
    "height",
    "n",
    "quality",
    "output_format",
    "background",
    "style",
    "moderation",
    "output_compression",
    "partial_images",
    "stream",
    "api_key",
)

try:
    from ..config.settings import load_config, save_config
    from ..services.router import NanaixRouter
    from ..utils.errors import prompt_required_message, required_key_message
    from ..utils.size_mapping import apply_resolution_preset
    from ..utils.validation import resolve_validation_node_inputs
except ImportError:  # pragma: no cover - local pytest import fallback
    from config.settings import load_config, save_config
    from services.router import NanaixRouter
    from utils.errors import prompt_required_message, required_key_message
    from utils.size_mapping import apply_resolution_preset
    from utils.validation import resolve_validation_node_inputs


class NanaixTextNode:
    CATEGORY = "Nanaix"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "generate"
    SEARCH_ALIASES = ["nanaix text", "nanaix generate", "nanaix image generate"]
    DESCRIPTION = (
        "Generate Nanaix images with ComfyUI-native IMAGE output. "
        "When n > 1, the node returns an IMAGE batch that still plugs directly into PreviewImage or SaveImage. "
        "New nodes prefill from saved local config when available, but an empty visible key still raises an error. "
        "Use resolution_preset for common sizes or custom width and height for manual control."
    )

    def __init__(self, router: NanaixRouter | None = None, config_path=None) -> None:
        self.router = router or NanaixRouter()
        self.config_path = config_path

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, tuple[object, dict[str, object]]]]:
        defaults = load_config()
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "dynamicPrompts": True,
                        "placeholder": "Describe the image you want to generate",
                        "tooltip": "Describe the image to generate. A more specific prompt usually produces more controllable results.",
                    },
                ),
                "model": (
                    "STRING",
                    {
                        "default": defaults["model"],
                        "placeholder": "Enter a Nanaix model name, for example gpt-image-2 or nano-banana-pro",
                        "tooltip": (
                            "Enter the Nanaix model name. Use gpt-image-* when you want image-2 controls such as "
                            "transparent background, style, moderation, compression, or SSE streaming. "
                            "Use nano-banana-* for the simpler shared path when you do not need those gpt-image-2-only controls. "
                            "This node routes by model family and always uses the single api_key field."
                        ),
                    },
                ),
                "resolution_preset": (
                    ["custom", "square", "square_2k", "square_4k", "landscape_hd", "portrait_hd", "landscape_2k", "portrait_2k", "landscape_4k", "portrait_4k"],
                    {
                        "default": defaults["resolution_preset"],
                        "tooltip": "Choose a resolution preset for common output sizes. Use custom to keep the width and height fields.",
                    },
                ),
                "width": ("INT", {"default": defaults["width"], "min": 1, "max": 4096, "tooltip": "Set the requested output width in pixels."}),
                "height": ("INT", {"default": defaults["height"], "min": 1, "max": 4096, "tooltip": "Set the requested output height in pixels."}),
                "n": (
                    "INT",
                    {
                        "default": defaults["n"],
                        "min": 1,
                        "max": 8,
                        "tooltip": "Choose the number of images to request in one run. When n > 1, the node returns a ComfyUI IMAGE batch that still connects directly to PreviewImage and SaveImage.",
                    },
                ),
                "quality": (["high", "medium", "low"], {"default": defaults["quality"], "tooltip": "Shared quality setting passed to the Nanaix backend."}),
                "output_format": (["png", "webp", "jpeg"], {"default": defaults["output_format"], "tooltip": "Preferred output file format for returned images."}),
                "background": (
                    ["auto", "transparent"],
                    {
                        "default": defaults["background"],
                        "tooltip": "Background mode. transparent is especially useful for gpt-image-2 PNG assets. Banana models currently ignore this field.",
                    },
                ),
                "style": (
                    ["natural", "vivid"],
                    {
                        "default": defaults["style"],
                        "tooltip": "Image style hint for gpt-image-2. vivid pushes a stronger stylized look. Banana models currently ignore this field.",
                    },
                ),
                "moderation": (
                    ["auto", "low"],
                    {
                        "default": defaults["moderation"],
                        "tooltip": "moderation level for gpt-image-2 requests. Banana models currently ignore this field.",
                    },
                ),
                "output_compression": (
                    "INT",
                    {
                        "default": defaults["output_compression"],
                        "min": 0,
                        "max": 100,
                        "tooltip": "Output compression level for gpt-image-2. Use 0 for the backend default. Banana models currently ignore this compression field.",
                    },
                ),
                "partial_images": (
                    "INT",
                    {
                        "default": defaults["partial_images"],
                        "min": 0,
                        "max": 8,
                        "tooltip": "Streamed preview segment count for gpt-image-2. Use 0 to disable partial image requests. Banana models currently ignore this field.",
                    },
                ),
                "stream": (
                    "BOOLEAN",
                    {
                        "default": defaults["stream"],
                        "tooltip": "Enable SSE streaming for gpt-image-2 requests and wait for the completed event before returning the final IMAGE output. Banana models currently ignore this field.",
                    },
                ),
                "api_key": (
                    "STRING",
                    {
                        "default": defaults["api_key"],
                        "placeholder": "Paste your Nanaix API key",
                        "tooltip": "Single API key field used for both gpt-image-* and nano-banana-* models.",
                    },
                ),
                "official_website": (
                    "STRING",
                    {
                        "default": "https://ai.nanaix.com",
                        "tooltip": "Nanaix official website. This display-only field is not sent to the API.",
                    },
                ),
            },
            "hidden": {
                "prompt_graph": "PROMPT",
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, prompt_graph):
        inputs = resolve_validation_node_inputs(prompt_graph)
        prompt = str(inputs.get("prompt", ""))
        model = str(inputs.get("model", ""))
        api_key = str(inputs.get("api_key", ""))

        if not prompt.strip():
            return prompt_required_message("Nanaix_Text")
        normalized_model = model.strip()
        if not normalized_model:
            return "model is required. Enter a Nanaix model name such as gpt-image-2 or nano-banana-pro."
        if not (
            normalized_model.startswith("gpt-image-") or normalized_model.startswith("nano-banana-")
        ):
            return (
                f"unsupported model {normalized_model}. "
                "Use a model name starting with gpt-image- or nano-banana-."
            )
        if not api_key.strip():
            return required_key_message(normalized_model, "api_key")
        return True

    def generate(self, **kwargs: object) -> tuple[object]:
        request_values = dict(kwargs)
        request_values["api_key"] = str(request_values.get("api_key", "")).strip()
        request_values["width"], request_values["height"] = apply_resolution_preset(
            str(request_values.get("resolution_preset", "custom")),
            int(request_values["width"]),
            int(request_values["height"]),
        )
        request_kwargs = {key: request_values[key] for key in ROUTER_INPUT_KEYS if key in request_values}
        image = self.router.run_text(**request_kwargs)
        save_config(request_values, self.config_path)
        return (image,)
