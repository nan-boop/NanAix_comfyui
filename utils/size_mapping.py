from math import gcd


IMAGE2_SIZES = (
    "1024x1024",
    "1536x1536",
    "1536x1024",
    "1024x1536",
    "2048x2048",
    "2048x1536",
    "1536x2048",
    "4096x4096",
    "4096x3072",
    "3072x4096",
)

BANANA_SIZE_BY_LONGEST_EDGE = (
    (1024, "1K"),
    (2048, "2K"),
    (4096, "4K"),
)

RESOLUTION_PRESETS = {
    "custom": None,
    "square": (1024, 1024),
    "square_2k": (2048, 2048),
    "square_4k": (4096, 4096),
    "landscape_hd": (1536, 1024),
    "portrait_hd": (1024, 1536),
    "landscape_2k": (2048, 1024),
    "portrait_2k": (1024, 2048),
    "landscape_4k": (4096, 3072),
    "portrait_4k": (3072, 4096),
}


def apply_resolution_preset(preset: str, width: int, height: int) -> tuple[int, int]:
    if preset not in RESOLUTION_PRESETS:
        raise ValueError(f"unknown resolution preset: {preset}")
    resolved = RESOLUTION_PRESETS[preset]
    if resolved is None:
        return width, height
    return resolved


def map_image2_size(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive integers")

    direct_size = f"{width}x{height}"
    if direct_size in IMAGE2_SIZES:
        return direct_size

    if width == height:
        return "1024x1024"
    if width > height:
        return "1536x1024"
    return "1024x1536"


def map_banana_size(width: int, height: int) -> tuple[str, str]:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive integers")

    ratio_gcd = gcd(width, height)
    aspect_ratio = f"{width // ratio_gcd}:{height // ratio_gcd}"
    longest_edge = max(width, height)

    chosen_size = "4K"
    for threshold, name in BANANA_SIZE_BY_LONGEST_EDGE:
        if longest_edge <= threshold:
            chosen_size = name
            break
    return aspect_ratio, chosen_size
