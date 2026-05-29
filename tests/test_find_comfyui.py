from __future__ import annotations

import sys
from pathlib import Path

from scripts import find_comfyui


def test_find_custom_nodes_candidates_returns_matching_directories(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    custom_nodes.mkdir(parents=True)

    results = find_comfyui.find_custom_nodes_candidates([tmp_path], limit=10)

    assert custom_nodes.resolve() in results


def test_find_custom_nodes_candidates_deduplicates_results(tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI" / "custom_nodes"
    custom_nodes.mkdir(parents=True)

    results = find_comfyui.find_custom_nodes_candidates([tmp_path, tmp_path], limit=10)

    assert results.count(custom_nodes.resolve()) == 1


def test_find_custom_nodes_candidates_respects_limit(tmp_path: Path) -> None:
    for index in range(3):
        (tmp_path / f"ComfyUI_{index}" / "custom_nodes").mkdir(parents=True)

    results = find_comfyui.find_custom_nodes_candidates([tmp_path], limit=2)

    assert len(results) == 2


def test_find_custom_nodes_candidates_prefers_real_comfy_layout_over_temp_paths(tmp_path: Path) -> None:
    temp_candidate = tmp_path / "pytest-of-z" / "pytest-123" / "ComfyUI" / "custom_nodes"
    real_candidate = tmp_path / "ComfyUI-aki-v3" / "ComfyUI" / "custom_nodes"
    temp_candidate.mkdir(parents=True)
    real_candidate.mkdir(parents=True)

    results = find_comfyui.find_custom_nodes_candidates([tmp_path], limit=10)

    assert results[0] == real_candidate.resolve()


def test_find_best_custom_nodes_candidate_returns_top_ranked_match(tmp_path: Path) -> None:
    (tmp_path / "pytest-of-z" / "pytest-123" / "ComfyUI" / "custom_nodes").mkdir(parents=True)
    real_candidate = tmp_path / "ComfyUI-aki-v3" / "ComfyUI" / "custom_nodes"
    real_candidate.mkdir(parents=True)

    result = find_comfyui.find_best_custom_nodes_candidate([tmp_path])

    assert result == real_candidate.resolve()


def test_find_best_comfy_python_candidate_prefers_embedded_python(tmp_path: Path) -> None:
    embedded = tmp_path / "ComfyUI-aki-v3" / "python" / "python.exe"
    other = tmp_path / "tools" / "python.exe"
    embedded.parent.mkdir(parents=True)
    other.parent.mkdir(parents=True)
    embedded.write_text("", encoding="utf-8")
    other.write_text("", encoding="utf-8")

    result = find_comfyui.find_best_comfy_python_candidate([tmp_path])

    assert result == embedded.resolve()


def test_main_prints_matching_python_candidate_for_custom_nodes(monkeypatch, capsys, tmp_path: Path) -> None:
    custom_nodes = tmp_path / "ComfyUI-aki-v3" / "ComfyUI" / "custom_nodes"
    python_executable = tmp_path / "ComfyUI-aki-v3" / "python" / "python.exe"
    custom_nodes.mkdir(parents=True)
    python_executable.parent.mkdir(parents=True)
    python_executable.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "find_comfyui.py",
            "--roots",
            str(tmp_path),
            "--limit",
            "5",
        ],
    )

    exit_code = find_comfyui.main()
    output_lines = capsys.readouterr().out.splitlines()

    assert exit_code == 0
    assert any(str(custom_nodes.resolve()) in line for line in output_lines)
    assert any(str(python_executable.resolve()) in line for line in output_lines)
