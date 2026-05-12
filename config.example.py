# Copy to mac/config.py and fill in your values
K10_IP   = "192.168.x.x"   # set after router DHCP reservation for K10's MAC address
K10_PORT = 8080
MAC_PORT = 8081

STATE_FILE = "~/.claudebox/state.json"
LOG_DIR    = "~/.claude/projects"

APPROVAL_REQUIRED = ["Bash"]
AUTO_ALLOW        = ["Read", "Glob", "Grep", "LS", "WebSearch", "WebFetch"]

SESSION_TYPICAL_MAX     = 150_000
IDLE_THRESHOLD_MINUTES  = 10
BROADCASTER_DEBOUNCE_S  = 1
SCANNER_INTERVAL_S      = 30
APPROVAL_TIMEOUT_S      = 60
