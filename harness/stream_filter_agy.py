"""Turn ``agy --output-format stream-json`` into a concise fixture log."""

import json
import os
import sys
import time


work = sys.argv[1] if len(sys.argv) > 1 else "."
log_path = os.path.join(work, "filtered.log")
t0 = time.time()
execute_count = 0


def stamp():
    return f"[{int(time.time() - t0):4d}s]"


def emit(line, key=False):
    with open(log_path, "a") as handle:
        handle.write(line + "\n")
    if key:
        print(line, flush=True)


def compact(value, limit=180):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, separators=(",", ":"))
    return str(value or "").replace("\n", " ").strip()[:limit]


for raw in sys.stdin:
    try:
        event = json.loads(raw)
    except Exception:
        continue

    kind = event.get("event", "")
    if kind == "init":
        init = event.get("init", {})
        emit(
            f"{stamp()} session model={init.get('model', '')} "
            f"mode={init.get('permission_mode', '')}",
            key=False,
        )
        continue

    if kind == "result":
        result = event.get("result", {})
        usage = result.get("usage", {})
        emit(
            f"{stamp()} RESULT {result.get('status', '')} "
            f"turns={result.get('num_turns', 0)} "
            f"in={usage.get('input_tokens', 0)} "
            f"out={usage.get('output_tokens', 0)} "
            f"thinking={usage.get('thinking_tokens', 0)}",
            key=True,
        )
        continue

    if kind not in ("step_update", "error"):
        continue
    if kind == "error":
        emit(f"{stamp()} ERROR: {compact(event)}", key=True)
        continue

    step = event.get("step_update", {})
    step_type = step.get("step_type", "")
    state = step.get("state", "")
    tool = step.get("tool_info") or {}

    if tool:
        # Agy emits ACTIVE and terminal updates for the same call. Log only the
        # terminal update so tool counts and published timelines are not doubled.
        if state == "ACTIVE":
            continue
        name = (
            tool.get("name")
            or step.get("tool_name")
            or tool.get("tool_name")
            or tool.get("canonical_name")
            or "tool"
        )
        params = tool.get("parameters") or tool.get("input") or {}
        output = tool.get("output") or tool.get("result") or ""
        # Agy dispatches MCP through call_mcp_tool; expose the actual inner tool.
        if name == "call_mcp_tool" and isinstance(params, dict):
            name = (
                params.get("ToolName")
                or params.get("tool_name")
                or params.get("name")
                or name
            )
            params = params.get("Arguments") or params.get("arguments") or params
        if str(name).endswith("execute"):
            execute_count += 1
            emit(f"{stamp()} execute #{execute_count}: {compact(params, 120)}", key=execute_count % 5 == 1)
        else:
            emit(f"{stamp()} . {name}: {compact(params, 100)}", key=False)
        low = compact(output, 240).lower()
        if low and any(token in low for token in ("validity gate", "exported", "gate fail", "error", "warning")):
            emit(f"{stamp()}   <- {compact(output, 200)}", key=True)
    elif step_type == "agent_response" and state == "DONE":
        text = compact(step.get("text_delta"), 240)
        if text:
            emit(f"{stamp()} chat: {text}", key=True)
    elif "error" in step_type or state == "FAILED":
        emit(f"{stamp()} {step_type} {state}: {compact(step)}", key=True)
