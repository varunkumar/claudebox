# Graph Report - .  (2026-05-18)

## Corpus Check
- Corpus is ~16,006 words - fits in a single context window. You may not need a graph.

## Summary
- 201 nodes · 250 edges · 44 communities (25 shown, 19 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 18 edges (avg confidence: 0.79)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Mac State & Broadcast|Mac State & Broadcast]]
- [[_COMMUNITY_Hook Settings & Permissions|Hook Settings & Permissions]]
- [[_COMMUNITY_K10 HTTP Server Lifecycle|K10 HTTP Server Lifecycle]]
- [[_COMMUNITY_K10 Approval UI|K10 Approval UI]]
- [[_COMMUNITY_Implementation Planning|Implementation Planning]]
- [[_COMMUNITY_K10 Display & Time|K10 Display & Time]]
- [[_COMMUNITY_Mood Tests|Mood Tests]]
- [[_COMMUNITY_Approval Integration Tests|Approval Integration Tests]]
- [[_COMMUNITY_RGB LED Control|RGB LED Control]]
- [[_COMMUNITY_Mood Engine|Mood Engine]]
- [[_COMMUNITY_I2C Sensor Drivers|I2C Sensor Drivers]]
- [[_COMMUNITY_Usage & Billing API|Usage & Billing API]]
- [[_COMMUNITY_Auto-Allow & Hook Relay|Auto-Allow & Hook Relay]]
- [[_COMMUNITY_Test Fixtures|Test Fixtures]]
- [[_COMMUNITY_Hook & Focus Tests|Hook & Focus Tests]]
- [[_COMMUNITY_JSONL Scanner|JSONL Scanner]]
- [[_COMMUNITY_PreToolUse Hook Config|PreToolUse Hook Config]]
- [[_COMMUNITY_Display Spec & Gotchas|Display Spec & Gotchas]]
- [[_COMMUNITY_Hardware Patterns|Hardware Patterns]]
- [[_COMMUNITY_Mood Threshold|Mood Threshold]]
- [[_COMMUNITY_Mac Config Template|Mac Config Template]]
- [[_COMMUNITY_K10 Device Config|K10 Device Config]]
- [[_COMMUNITY_Scanner Test (unknown sessions)|Scanner Test (unknown sessions)]]
- [[_COMMUNITY_Scanner Test (cost)|Scanner Test (cost)]]
- [[_COMMUNITY_Scanner Test (empty)|Scanner Test (empty)]]
- [[_COMMUNITY_Mood Test (happy)|Mood Test (happy)]]
- [[_COMMUNITY_Mood Test (neutral)|Mood Test (neutral)]]
- [[_COMMUNITY_Mood Test (tired)|Mood Test (tired)]]
- [[_COMMUNITY_Mood Test (sleeping)|Mood Test (sleeping)]]
- [[_COMMUNITY_Mood Test (cap)|Mood Test (cap)]]
- [[_COMMUNITY_State Test (missing)|State Test (missing)]]
- [[_COMMUNITY_State Test (roundtrip)|State Test (roundtrip)]]
- [[_COMMUNITY_State Test (concurrent)|State Test (concurrent)]]
- [[_COMMUNITY_Developer Notes|Developer Notes]]
- [[_COMMUNITY_Port Retry Pattern|Port Retry Pattern]]

## God Nodes (most connected - your core abstractions)
1. `_Handler` - 14 edges
2. `render()` - 10 edges
3. `handle_request()` - 10 edges
4. `_broadcaster_loop()` - 9 edges
5. `Permission Request Handler` - 9 edges
6. `_tokens()` - 8 edges
7. `update()` - 8 edges
8. `show_approval()` - 7 edges
9. `_scanner_loop()` - 7 edges
10. `read()` - 7 edges

## Surprising Connections (you probably didn't know these)
- `Usage Bar Display Description` --references--> `fetch_usage()`  [INFERRED]
  README.md → mac/usage.py
- `Approval Gate Documentation` --references--> `Permission Request Handler`  [INFERRED]
  README.md → mac/server.py
- `Broadcaster Must Not Push environment Field` --rationale_for--> `_broadcaster_loop()`  [EXTRACTED]
  CLAUDE.md → mac/server.py
- `Dashboard Payload Schema (Spec §8)` --references--> `_broadcaster_loop()`  [EXTRACTED]
  docs/specs/2026-05-12-claudebox-mac-k10-design.md → mac/server.py
- `Mood RGB LED Color Table` --references--> `Mood Threshold Table (_THRESHOLDS)`  [INFERRED]
  README.md → mac/mood.py

## Hyperedges (group relationships)
- **k10_base Timer Kill Pattern (RGB, Approval, Main)** — device_rgb_lazy_init_rationale, device_approval_timer_kill_before_tcp, device_main_kill_k10_timers [EXTRACTED 0.95]
- **K10 HTTP Server Request-Response-Render Cycle** — device_main_start_server, device_main_handle_request, device_main_do_render [EXTRACTED 1.00]
- **K10-side Approval Flow: Receive, Display, Decide, Respond** — device_main_approve_endpoint, device_approval_show_approval, device_approval_post_decision [EXTRACTED 1.00]
- **Approval Flow: PermissionRequest to K10 Decision** — mac_server_handle_permission_request, mac_server_pending_approvals, mac_server_handle_decision [EXTRACTED 1.00]
- **Thread-Safe State Access Pattern** — mac_state_lock, mac_state_read, mac_state_update [EXTRACTED 1.00]
- **Broadcaster: Mood Compute and Push Pipeline** — mac_server_broadcaster_loop, mac_mood_compute_mood, mac_server_broadcast_event [EXTRACTED 1.00]

## Communities (44 total, 19 thin omitted)

### Community 0 - "Mac State & Broadcast"
Cohesion: 0.15
Nodes (19): Broadcaster Must Not Push environment Field, Dashboard Payload Schema (Spec §8), State JSON Schema (Spec §7), iTerm2 FocusMonitor Daemon, main(), _notify(), Broadcast Event (threading.Event), _broadcaster_loop() (+11 more)

### Community 1 - "Hook Settings & Permissions"
Cohesion: 0.18
Nodes (10): Claude Code Hooks Configuration, permissions, allow, _Handler, main(), make_server(), ThreadingHTTPServer, _ThreadingHTTPServer (+2 more)

### Community 2 - "K10 HTTP Server Lifecycle"
Cohesion: 0.24
Nodes (14): boot(), connect_wifi(), do_render(), handle_request(), _kill_k10_timers(), parse_request(), Port Bind Retry Loop (SO_REUSEADDR Unreliable), Kill k10_base timers to prevent I2C contention. (+6 more)

### Community 3 - "K10 Approval UI"
Cohesion: 0.19
Nodes (13): APPROVAL_REQUIRED List, _draw_header(), _draw_screen(), _init_approval_buttons(), _init_approval_buttons(): Button Hardware Init, k10_base Module Cache Eviction for Fresh I2C, _post_decision(), Blank screen and reset layer state so display.py's show_draw() works cleanly. (+5 more)

### Community 4 - "Implementation Planning"
Cohesion: 0.15
Nodes (14): Implementation Plan Build Order, Phase 1: Mac Foundation Tasks, Phase 2: K10 Firmware Tasks, Phase 3: Integration Tasks, Approval Flow Design (Spec §5.1), APPROVAL_REQUIRED Tool List, AUTO_ALLOW Tool List, K10 Network Configuration (K10_IP, K10_PORT, MAC_PORT) (+6 more)

### Community 5 - "K10 Display & Time"
Cohesion: 0.29
Nodes (9): TZ_OFFSET_S: Timezone Offset for Display, _draw_spikes(), init() Reset Pattern for Re-render, _k(), Lazy Screen Init with Timer Kill Pattern, MOOD_COLOR: Mood-to-Color Map, render(), _render_console() (+1 more)

### Community 6 - "Mood Tests"
Cohesion: 0.42
Nodes (8): test_happy_below_20_percent(), test_neutral_between_20_and_50(), test_score_capped_at_1(), test_sleeping_idle_overrides_even_high_tokens(), test_sleeping_overrides_score_when_idle(), test_stressed_above_75(), test_tired_between_50_and_75(), _tokens()

### Community 7 - "Approval Integration Tests"
Cohesion: 0.42
Nodes (8): _mock_k10_server(), _post(), Start a mock K10 that receives /approve and immediately sends /decision back., test_approval_auto_allows_non_approval_required_tools(), test_approval_background_session_gets_ask(), test_approval_k10_unreachable_returns_ask(), test_approval_roundtrip_allow(), test_approval_roundtrip_deny()

### Community 8 - "RGB LED Control"
Cohesion: 0.50
Nodes (7): _beep(), _fill(), flash_mood(), _get_np(), Lazy RGB Init to Defer k10_base Timer, _MOOD_COLORS: Mood-to-RGB Map, set_mood()

### Community 9 - "Mood Engine"
Cohesion: 0.29
Nodes (6): SESSION_TYPICAL_MAX Mood Calibration, compute_mood(), Idle Override to Sleeping Mood, Return (mood_name, mood_score). Sleeping overrides score if idle long enough., Mood Threshold Table (_THRESHOLDS), Mood RGB LED Color Table

### Community 10 - "I2C Sensor Drivers"
Cohesion: 0.53
Nodes (5): Fresh I2C Instance Per Read (Rationale), _make_i2c(), _read_aht20(), _read_ltr303(), read_sensors()

### Community 11 - "Usage & Billing API"
Cohesion: 0.40
Nodes (5): Rate-Limit Backoff (1 hour on 429), fetch_usage(), _get_access_token(), Return {'five_hour_pct': float, 'seven_day_pct': float}, or None if rate-limited, Usage Bar Display Description

### Community 14 - "Auto-Allow & Hook Relay"
Cohesion: 0.40
Nodes (5): AUTO_ALLOW List, iTerm Session ID Injection, PermissionRequest Decision via stdout, hook.py: Hook Relay Script, Server Endpoint: /hook (localhost:8081)

### Community 15 - "Test Fixtures"
Cohesion: 0.40
Nodes (3): unused_tcp_port(), test_scan_aggregates_tokens_for_known_sessions, test_scanner_thread_updates_tokens_in_state

### Community 16 - "Hook & Focus Tests"
Cohesion: 0.70
Nodes (4): _post(), test_focus_endpoint_updates_active_iterm(), test_post_tool_use_updates_last_tool(), test_session_start_hook_creates_session_entry()

### Community 17 - "JSONL Scanner"
Cohesion: 0.67
Nodes (3): Context Window Token Limit (200K), _scan_file(), scan_sessions()

## Knowledge Gaps
- **43 isolated node(s):** `PreToolUse`, `allow`, `iTerm Session ID Injection`, `Server Endpoint: /hook (localhost:8081)`, `config.example.py: Mac-side Config Template` (+38 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Permission Request Handler` connect `Implementation Planning` to `Mac State & Broadcast`, `Hook Settings & Permissions`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Why does `_Handler` connect `Hook Settings & Permissions` to `Mac State & Broadcast`, `Implementation Planning`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `_scanner_loop()` connect `Mac State & Broadcast` to `Hook Settings & Permissions`, `Usage & Billing API`, `JSONL Scanner`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **What connects `Force-reload k10_base to get a fresh I2C state, then create buttons.`, `Blank screen and reset layer state so display.py's show_draw() works cleanly.`, `Kill k10_base timers to prevent I2C contention.` to the rest of the system?**
  _62 weakly-connected nodes found - possible documentation gaps or missing edges._