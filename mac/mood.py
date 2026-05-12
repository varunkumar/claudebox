import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import config

SESSION_TYPICAL_MAX    = config.SESSION_TYPICAL_MAX
IDLE_THRESHOLD_MINUTES = config.IDLE_THRESHOLD_MINUTES

_THRESHOLDS = [
    (0.20, "happy"),
    (0.50, "neutral"),
    (0.75, "tired"),
    (1.01, "stressed"),
]


def compute_mood(tokens: dict, idle_minutes: float) -> tuple:
    """Return (mood_name, mood_score). Sleeping overrides score if idle long enough."""
    if idle_minutes >= IDLE_THRESHOLD_MINUTES:
        return "sleeping", 0.0

    raw = (tokens["input"] + tokens["output"]) / SESSION_TYPICAL_MAX
    score = min(raw, 1.0)

    for threshold, name in _THRESHOLDS:
        if score < threshold:
            return name, score

    return "stressed", score
