import glob
import json
import os

PRICING = {
    "claude-opus-4-6":   {"input": 6.15,  "output": 30.75, "cache_write": 7.69,  "cache_read": 0.61},
    "claude-sonnet-4-6": {"input": 3.69,  "output": 18.45, "cache_write": 4.61,  "cache_read": 0.37},
    "claude-haiku-4-5":  {"input": 1.23,  "output": 6.15,  "cache_write": 1.54,  "cache_read": 0.12},
}
_DEFAULT_PRICING = PRICING["claude-sonnet-4-6"]


def scan_sessions(log_dir: str, session_ids: set) -> dict:
    """Aggregate token usage from JSONL files for the given session IDs."""
    totals = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "cost_usd": 0.0}
    if not session_ids:
        return totals

    pattern = os.path.join(os.path.expanduser(log_dir), "**", "*.jsonl")
    for path in glob.glob(pattern, recursive=True):
        _scan_file(path, session_ids, totals)

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
                if entry.get("session_id") not in session_ids:
                    continue
                _accumulate(entry, totals)
    except OSError:
        pass


def _accumulate(entry: dict, totals: dict) -> None:
    msg = entry.get("message", {})
    usage = msg.get("usage", {})
    model = msg.get("model", "claude-sonnet-4-6")
    price = PRICING.get(model, _DEFAULT_PRICING)

    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    cw  = usage.get("cache_creation_input_tokens", 0)
    cr  = usage.get("cache_read_input_tokens", 0)

    totals["input"]       += inp
    totals["output"]      += out
    totals["cache_write"] += cw
    totals["cache_read"]  += cr
    totals["cost_usd"]    += (
        inp * price["input"]       / 1_000_000 +
        out * price["output"]      / 1_000_000 +
        cw  * price["cache_write"] / 1_000_000 +
        cr  * price["cache_read"]  / 1_000_000
    )
