# Nanaix_Text

Generate images from a text prompt using Nanaix image models.

## Supported models

- `gpt-image-2`
- `nano-banana-2`
- `nano-banana-pro`

If you want image-2-specific controls such as transparent background, style, moderation, output compression, or SSE streaming, choose `gpt-image-2`. If you just want the simpler shared Nanaix path and do not need those `gpt-image-2`-only controls, choose `nano-banana-2` or `nano-banana-pro`.

## Required fields

- `prompt`
- `model`
- `api_key`

Use the single visible `api_key` field for the selected model. If the model starts with `gpt-image-`, paste an image-2 key. If the model starts with `nano-banana-`, paste a nano-banana key.

## Common parameters

- `resolution_preset`: Common size shortcuts. Use `custom` to keep manual `width` and `height`
- `width` / `height`: Requested output size
- `n`: Number of images to request. When `n > 1`, the node returns an image batch that still connects directly to `PreviewImage` and `SaveImage`
- `quality`: Shared quality selector used by the node
- `output_format`: Output format preference
- `background`: `auto` or `transparent`. This is most useful with `gpt-image-2`
- `style`: `natural` or `vivid`. This is most useful with `gpt-image-2`
- `moderation`: `auto` or `low`. This is most useful with `gpt-image-2`
- `output_compression`: `0` to `100`. `0` keeps the backend default and is most useful with `gpt-image-2`
- `partial_images`: `0` to `8`. `0` disables partial image requests and is most useful with `gpt-image-2`
- `stream`: `true` or `false`. When enabled, `gpt-image-2` uses SSE and the node waits for the completed event before returning the final `IMAGE`

## Resolution presets

- `custom`: Keep the entered `width` and `height`
- `square -> 1024x1024`
- `square_2k -> 2048x2048`
- `square_4k -> 4096x4096`
- `landscape_hd -> 1536x1024`
- `portrait_hd -> 1024x1536`
- `landscape_2k -> 2048x1024`
- `portrait_2k -> 1024x2048`
- `landscape_4k -> 4096x3072`
- `portrait_4k -> 3072x4096`

## Output

Returns a ComfyUI `IMAGE`.

- If one image is returned, the output is a single image
- When `n > 1`, the node returns an image batch
- That image batch is still standard ComfyUI `IMAGE` data, so it can go straight into `PreviewImage` and `SaveImage`

## Notes

- Successful runs save the current keys and common parameters into local plugin config
- New node instances try to prefill those saved values automatically
- Saved config is only used to prefill newly created nodes; leaving the visible key blank still raises an error
- If the selected model is missing a key, the node tells you to fill `api_key` directly in the error message
- `background=transparent` is intended for `gpt-image-2`. Nano-banana models currently ignore that field
- `style` and `moderation` are also intended for `gpt-image-2`. Nano-banana models currently ignore those fields
- `output_compression` is also intended for `gpt-image-2`. Nano-banana models currently ignore that field
- `partial_images` is also intended for `gpt-image-2` streamed partial image segments. Nano-banana models currently ignore that field
- `stream` is also intended for `gpt-image-2` SSE requests. The node still returns only the final completed image result, and nano-banana models currently ignore this field
- If you set those `gpt-image-2`-only controls while using `nano-banana-*`, the runtime now raises a warning that lists the ignored fields
- `gpt-image-2` also preserves several common custom sizes directly, including `2048x2048`, `2048x1536`, `1536x2048`, `4096x4096`, `4096x3072`, and `3072x4096`
- If you want to test your key outside ComfyUI, use `scripts/smoke_test.py`
