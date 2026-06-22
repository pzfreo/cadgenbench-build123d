"""Turn `codex exec --json` (on stdin) into a readable live log.

Codex counterpart of stream_filter.py. Codex's event schema differs from Claude
Code's: top-level events are dotted types (thread.started / turn.started /
item.started / item.completed / turn.completed), and tool calls / agent text are
carried inside `item` objects keyed by item.type (agent_message, reasoning,
command_execution, mcp_tool_call, view_image_tool_call, ...). Non-JSON lines
(e.g. Codex's cosmetic shell_snapshot warnings) are ignored.

Writes every event concisely to <work_dir>/filtered.log (full timeline) and
prints high-signal events to stdout (build123d tool calls, validate/export
results, errors, agent reasoning) so a stuck loop or repeated error is visible
live.

Usage:
  tail -n0 -f <work_dir>/stream.jsonl | python3 harness/stream_filter_codex.py <work_dir>
"""

import json
import os
import sys
import time

work = sys.argv[1] if len(sys.argv) > 1 else "."
LOG = os.path.join(work, "filtered.log")
t0 = time.time()
n_build = 0


def stamp():
    return f"[{int(time.time() - t0):4d}s]"


def emit(line, key=False):
    with open(LOG, "a") as f:
        f.write(line + "\n")
    if key:
        print(line, flush=True)


def first(d, *keys, default=""):
    for k in keys:
        v = d.get(k)
        if v:
            return v
    return default


def handle_item(item):
    """One completed Codex item -> at most one log line."""
    global n_build
    itype = item.get("type", "")

    if itype in ("agent_message", "assistant_message"):
        txt = first(item, "text", "message").strip()
        if txt:
            emit(f"{stamp()} chat: {txt[:200]}", key=True)

    elif itype in ("reasoning", "agent_reasoning"):
        txt = first(item, "text", "summary").strip().replace("\n", " ")
        if txt:
            emit(f"{stamp()} think: {txt[:160]}", key=False)

    elif itype in ("mcp_tool_call", "tool_call"):
        # build123d tool calls — the substance of the run. Codex may name the tool
        # any of several ways depending on version (bare "execute", or namespaced
        # "build123d__execute" / "build123d.execute" / "mcp__build123d__execute"),
        # so strip whatever server prefix is present.
        name = first(item, "tool_name", "tool", "name")
        for pre in ("mcp__build123d__", "build123d__", "build123d.", "build123d:", "build123d_"):
            if name.startswith(pre):
                name = name[len(pre):]
                break
        args = item.get("arguments", item.get("input", {})) or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        result = item.get("result", item.get("output", ""))
        if isinstance(result, (dict, list)):
            result = json.dumps(result)
        result = str(result).replace("\n", " ").strip()
        low = result.lower()
        if name == "execute":
            n_build += 1
            code = (args.get("code", "") or "").replace("\n", " ")[:90]
            emit(f"{stamp()} execute #{n_build}: {code}", key=(n_build % 5 == 1))
        elif name in ("validate", "export"):
            arg = args.get("object_name", args.get("filename", ""))
            emit(f"{stamp()} >> {name}({arg})", key=True)
        else:
            emit(f"{stamp()} . {name}", key=False)
        if result:
            key = any(
                k in low
                for k in (
                    "validity gate",
                    "exported",
                    "gate fail",
                    "error",
                    "warning",
                    "non-manifold",
                    "open edge",
                )
            )
            emit(f"{stamp()}   <- {result[:160]}", key=key)

    elif itype in ("command_execution", "exec_command", "local_shell_call"):
        cmd = first(item, "command", "cmd")
        if isinstance(cmd, list):
            cmd = " ".join(str(c) for c in cmd)
        emit(f"{stamp()} $ {str(cmd).replace(chr(10), ' ')[:120]}", key=False)

    elif itype in ("view_image_tool_call", "view_image"):
        p = first(item, "path", "image_path")
        emit(f"{stamp()} . view_image({p})", key=False)

    elif itype == "error":
        emit(f"{stamp()} ERROR: {first(item, 'message', 'text')[:160]}", key=True)

    else:
        emit(f"{stamp()} ~ {itype}", key=False)


for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue
    try:
        ev = json.loads(raw)
    except Exception:
        continue  # non-JSON noise (e.g. shell_snapshot warnings)
    t = ev.get("type", "")

    if t in ("item.completed", "item.started"):
        # only log completed items to avoid double-printing each tool call
        if t == "item.completed":
            handle_item(ev.get("item", {}) or {})
    elif t == "thread.started":
        emit(f"{stamp()} session {ev.get('thread_id', '')}", key=False)
    elif t == "turn.completed":
        u = ev.get("usage", {}) or {}
        emit(
            f"{stamp()} RESULT tokens in={u.get('input_tokens', 0)} "
            f"out={u.get('output_tokens', 0)}",
            key=True,
        )
    elif t in ("error", "stream_error"):
        emit(f"{stamp()} STREAM ERROR: {str(ev)[:160]}", key=True)
