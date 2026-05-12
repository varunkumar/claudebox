import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mac'))

import mood

def _tokens(inp, out):
    return {"input": inp, "output": out, "cache_write": 0, "cache_read": 0, "cost_usd": 0.0}

def test_happy_below_20_percent():
    t = _tokens(25_000, 4_000)  # 29k / 150k = 19.3%
    name, score = mood.compute_mood(t, idle_minutes=0)
    assert name == "happy"
    assert score < 0.20

def test_neutral_between_20_and_50():
    t = _tokens(50_000, 10_000)  # 60k / 150k = 40%
    name, score = mood.compute_mood(t, idle_minutes=0)
    assert name == "neutral"
    assert 0.20 <= score < 0.50

def test_tired_between_50_and_75():
    t = _tokens(90_000, 15_000)  # 105k / 150k = 70%
    name, score = mood.compute_mood(t, idle_minutes=0)
    assert name == "tired"
    assert 0.50 <= score < 0.75

def test_stressed_above_75():
    t = _tokens(120_000, 20_000)  # 140k / 150k = 93%
    name, score = mood.compute_mood(t, idle_minutes=0)
    assert name == "stressed"
    assert score >= 0.75

def test_sleeping_overrides_score_when_idle():
    t = _tokens(0, 0)
    name, score = mood.compute_mood(t, idle_minutes=11)
    assert name == "sleeping"

def test_sleeping_idle_overrides_even_high_tokens():
    t = _tokens(200_000, 50_000)
    name, score = mood.compute_mood(t, idle_minutes=15)
    assert name == "sleeping"

def test_score_capped_at_1():
    t = _tokens(500_000, 500_000)
    name, score = mood.compute_mood(t, idle_minutes=0)
    assert score <= 1.0
