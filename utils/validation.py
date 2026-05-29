from __future__ import annotations

import inspect


def get_prompt_node_inputs(prompt_graph: object, node_id: object) -> dict[str, object]:
    if not isinstance(prompt_graph, dict):
        return {}

    node = prompt_graph.get(str(node_id))
    if not isinstance(node, dict):
        return {}

    inputs = node.get("inputs")
    if not isinstance(inputs, dict):
        return {}

    return inputs


def resolve_validation_node_inputs(prompt_graph: object) -> dict[str, object]:
    current_prompt = prompt_graph if isinstance(prompt_graph, dict) and prompt_graph else None
    current_node_id = None

    frame = inspect.currentframe()
    try:
        while frame is not None:
            if frame.f_code.co_name == "validate_inputs":
                prompt_candidate = frame.f_locals.get("prompt")
                node_id_candidate = frame.f_locals.get("unique_id")
                if current_prompt is None and isinstance(prompt_candidate, dict):
                    current_prompt = prompt_candidate
                if node_id_candidate is not None:
                    current_node_id = node_id_candidate
                if current_prompt is not None and current_node_id is not None:
                    break
            frame = frame.f_back
    finally:
        del frame

    if current_prompt is None:
        return {}

    if current_node_id is not None:
        return get_prompt_node_inputs(current_prompt, current_node_id)

    if len(current_prompt) == 1:
        only_node_id = next(iter(current_prompt))
        return get_prompt_node_inputs(current_prompt, only_node_id)

    return {}
