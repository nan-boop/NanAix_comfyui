from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_ROOTS = [Path("C:/"), Path("D:/"), Path("E:/"), Path("F:/"), Path.home()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find likely ComfyUI custom_nodes directories on this machine.")
    parser.add_argument(
        "--roots",
        nargs="*",
        default=[str(root) for root in DEFAULT_ROOTS],
        help="Optional roots to scan. Defaults to common drive roots and the current home directory.",
    )
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of results to print")
    return parser.parse_args()


def score_custom_nodes_candidate(path: Path) -> tuple[int, int, int, str]:
    resolved = path.resolve()
    path_text = str(resolved).lower()
    parts = {part.lower() for part in resolved.parts}

    real_layout_score = 0
    if "comfyui" in parts:
        real_layout_score += 2
    if any(part.startswith("comfyui") and part != "comfyui" for part in parts):
        real_layout_score += 1

    temp_penalty = 1 if any(marker in path_text for marker in ("pytest-", "temp", "tmp")) else 0
    depth_bonus = len(resolved.parts)
    return (real_layout_score, -temp_penalty, depth_bonus, path_text)


def find_custom_nodes_candidates(roots: list[Path], limit: int = 20) -> list[Path]:
    results: list[Path] = []
    seen: set[str] = set()

    for root in roots:
        if not root.exists():
            continue
        try:
            for path in root.rglob("custom_nodes"):
                if not path.is_dir():
                    continue
                key = str(path.resolve())
                if key in seen:
                    continue
                seen.add(key)
                results.append(path.resolve())
        except (PermissionError, OSError):
            continue

    ranked = sorted(results, key=score_custom_nodes_candidate, reverse=True)
    return ranked[:limit]


def find_best_custom_nodes_candidate(roots: list[Path], limit: int = 20) -> Path | None:
    candidates = find_custom_nodes_candidates(roots, limit=limit)
    if not candidates:
        return None
    return candidates[0]


def score_comfy_python_candidate(path: Path) -> tuple[int, int, int, str]:
    resolved = path.resolve()
    path_text = str(resolved).lower()
    parts = {part.lower() for part in resolved.parts}

    comfy_score = 0
    if "comfyui" in parts:
        comfy_score += 2
    if "python" in parts:
        comfy_score += 1
    if any(part.startswith("comfyui") and part != "comfyui" for part in parts):
        comfy_score += 1

    temp_penalty = 1 if any(marker in path_text for marker in ("pytest-", "temp", "tmp")) else 0
    depth_bonus = len(resolved.parts)
    return (comfy_score, -temp_penalty, depth_bonus, path_text)


def find_comfy_python_candidates(roots: list[Path], limit: int = 20) -> list[Path]:
    results: list[Path] = []
    seen: set[str] = set()

    for root in roots:
        if not root.exists():
            continue
        try:
            for path in root.rglob("python.exe"):
                if not path.is_file():
                    continue
                key = str(path.resolve())
                if key in seen:
                    continue
                seen.add(key)
                results.append(path.resolve())
        except (PermissionError, OSError):
            continue

    ranked = sorted(results, key=score_comfy_python_candidate, reverse=True)
    return ranked[:limit]


def find_best_comfy_python_candidate(roots: list[Path], limit: int = 20) -> Path | None:
    candidates = find_comfy_python_candidates(roots, limit=limit)
    if not candidates:
        return None
    return candidates[0]


def find_matching_python_for_custom_nodes(custom_nodes_path: Path, limit: int = 20) -> Path | None:
    roots = [custom_nodes_path.parent, custom_nodes_path.parent.parent]
    return find_best_comfy_python_candidate([root for root in roots if root.exists()], limit=limit)


def main() -> int:
    args = parse_args()
    roots = [Path(root) for root in args.roots]
    results = find_custom_nodes_candidates(roots, limit=args.limit)
    for path in results:
        python_candidate = find_matching_python_for_custom_nodes(path, limit=args.limit)
        python_text = str(python_candidate) if python_candidate is not None else "none"
        print(f"custom_nodes={path} | python={python_text}")
    if not results:
        print("No custom_nodes directories found in the scanned roots.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
