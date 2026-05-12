import glob
import json
import os

CONTEXT_WINDOW = 200_000


def scan_sessions(log_dir: str, session_ids: set) -> dict:
    totals = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0,
              "context_tokens": 0, "context_pct": 0.0}
    if not session_ids:
        return totals

    pattern = os.path.join(os.path.expanduser(log_dir), "**", "*.jsonl")
    for path in glob.glob(pattern, recursive=True):
        _scan_file(path, session_ids, totals)

    totals["context_pct"] = min(totals["context_tokens"] / CONTEXT_WINDOW, 1.0)
    return totals


def _scan_file(path: str, session_ids: set, totals: dict) -> None:
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("sessionId") not in session_ids:
                    continue
                usage = entry.get("message", {}).get("usage", {})
                totals["input"]       += usage.get("input_tokens", 0)
                totals["output"]      += usage.get("output_tokens", 0)
                totals["cache_write"] += usage.get("cache_creation_input_tokens", 0)
                totals["cache_read"]  += usage.get("cache_read_input_tokens", 0)
                ctx = (usage.get("input_tokens", 0)
                       + usage.get("cache_creation_input_tokens", 0)
                       + usage.get("cache_read_input_tokens", 0))
                if ctx > totals["context_tokens"]:
                    totals["context_tokens"] = ctx
    except OSError:
        pass


