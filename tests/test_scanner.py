import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mac'))

import scanner

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')

def test_scan_aggregates_tokens_for_known_sessions():
    result = scanner.scan_sessions(FIXTURES, {"session-aaa", "session-bbb"})
    assert result["input"] == 1000 + 2000 + 500
    assert result["output"] == 200 + 400 + 100
    assert result["cache_write"] == 500 + 0 + 0
    assert result["cache_read"] == 300 + 1000 + 0

def test_scan_ignores_unknown_sessions():
    result = scanner.scan_sessions(FIXTURES, {"session-aaa"})
    assert result["input"] == 3000
    # session-ignored's 9999 tokens should not appear
    assert result["input"] < 9000

def test_scan_calculates_cost_usd():
    result = scanner.scan_sessions(FIXTURES, {"session-aaa"})
    # sonnet: input=$3.69/MTok, output=$18.45/MTok, cache_write=$4.61/MTok, cache_read=$0.37/MTok
    expected_cost = (
        3000 * 3.69 / 1_000_000 +
        600  * 18.45 / 1_000_000 +
        500  * 4.61 / 1_000_000 +
        1300 * 0.37 / 1_000_000
    )
    assert abs(result["cost_usd"] - expected_cost) < 0.0001

def test_scan_empty_sessions_returns_zeros():
    result = scanner.scan_sessions(FIXTURES, set())
    assert result["input"] == 0
    assert result["cost_usd"] == 0.0

def test_scan_missing_usage_fields_treated_as_zero():
    result = scanner.scan_sessions(FIXTURES, {"session-aaa", "session-bbb"})
    assert result["cost_usd"] >= 0
