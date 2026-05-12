import json
import subprocess
import urllib.error
import urllib.request


_KEYCHAIN_SERVICE = "Claude Code-credentials"
_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
_BETA_HEADER = "oauth-2025-04-20"


def _get_access_token() -> str:
    raw = subprocess.check_output(
        ["security", "find-generic-password", "-s", _KEYCHAIN_SERVICE, "-w"],
        stderr=subprocess.DEVNULL,
    )
    creds = json.loads(raw.decode().strip())
    return creds["claudeAiOauth"]["accessToken"]


_backoff_until: float = 0.0


def fetch_usage() -> dict | None:
    """Return {'five_hour_pct': float, 'seven_day_pct': float}, or None if rate-limited."""
    import time
    global _backoff_until
    if time.time() < _backoff_until:
        return None
    try:
        token = _get_access_token()
        req = urllib.request.Request(
            _USAGE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "anthropic-beta": _BETA_HEADER,
            },
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        return {
            "five_hour_pct": (data.get("five_hour") or {}).get("utilization", 0.0) / 100.0,
            "seven_day_pct": (data.get("seven_day") or {}).get("utilization", 0.0) / 100.0,
        }
    except urllib.error.HTTPError as e:
        if e.code == 429:
            _backoff_until = time.time() + 3600  # back off 1 hour on rate limit
            print(f"[usage] rate limited — pausing 1 hour", flush=True)
        else:
            print(f"[usage] API fetch failed: {e}", flush=True)
        return None
    except Exception as e:
        print(f"[usage] API fetch failed: {e}", flush=True)
        return None
