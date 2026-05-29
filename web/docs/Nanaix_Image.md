# Nanaix_Image

Edit or regenerate images from one or more reference images using Nanaix image models.

## Supported models

- `gpt-image-2`
- `nano-banana-2`
- `nano-banana-pro`

If you want image-2-specific controls such as transparent background, style, moderation, output compression, or SSE streaming during edits, choose `gpt-image-2`. If you just want the simpler shared Nanaix path and do not need those `gpt-image-2`-only controls, choose `nano-banana-2` or `nano-banana-pro`.

## Required fields

- `prompt`
- `model`
- `api_key`
- At least one connected reference image

Use the single visible `api_key` field for the selected model. If the model starts with `gpt-image-`, paste an image-2 key. If the model starts with `nano-banana-`, paste a nano-banana key.

## Reference image inputs

This node exposes up to 8 optional image inputs:

- `image_1`
- `image_2`
- `image_3`
- `image_4`
- `image_5`
- `image_6`
- `image_7`
- `image_8`

Connect at least one image input before queueing the workflow. `image_1` is the best place to start for a single-image edit.

For multi-reference edits, a good default pattern is:

- `image_1`: main subject, silhouette, or composition anchor
- `image_2`: secondary style, lighting, palette, or environment cue

If any connected input is itself a batch, the node expands that batch into individual reference images before calling the backend.

## Common parameters

- `prompt`: Describe the final image you want. For multi-reference edits, a good pattern is "keep the subject from image_1 and apply the style from image_2"
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

- The current MVP does not expose mask input
- Successful runs save the current keys and common parameters into local plugin config
- New node instances try to prefill those saved values automatically
- Saved config is only used to prefill newly created nodes; leaving the visible key blank still raises an error
- If no reference image or `api_key` is present, the node error tells you exactly what to connect or fill before queueing again
- `background=transparent` is intended for `gpt-image-2` edits. Nano-banana models currently ignore that field
- `style` and `moderation` are also intended for `gpt-image-2` edits. Nano-banana models currently ignore those fields
- `output_compression` is also intended for `gpt-image-2` edits. Nano-banana models currently ignore that field
- `partial_images` is also intended for `gpt-image-2` streamed partial image segments. Nano-banana models currently ignore that field
- `stream` is also intended for `gpt-image-2` SSE edit requests. The node still returns only the final completed image result, and nano-banana models currently ignore this field
- If you set those `gpt-image-2`-only controls while using `nano-banana-*`, the runtime now raises a warning that lists the ignored fields
- `gpt-image-2` also preserves several common custom sizes directly, including `2048x2048`, `2048x1536`, `1536x2048`, `4096x4096`, `4096x3072`, and `3072x4096`
