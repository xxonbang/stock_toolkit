import pytest
from modules.pattern_matcher import normalize_pattern, calculate_similarity, find_similar_patterns

def test_normalize_pattern():
    prices = [100, 105, 103, 110, 108]
    result = normalize_pattern(prices)
    assert result[0] == 0.0
    assert abs(result[1] - 5.0) < 0.01
    assert len(result) == 5

def test_calculate_similarity():
    p1 = [0, 5, 3, 10, 8]
    p2 = [0, 4, 2, 9, 7]
    sim = calculate_similarity(p1, p2)
    assert sim > 0.9

def test_calculate_similarity_different():
    p1 = [0, 5, 10, 15, 20]
    p2 = [0, -5, -10, -15, -20]
    sim = calculate_similarity(p1, p2)
    assert sim < 0.3

def test_find_similar_patterns():
    current = [100, 105, 103, 110, 108]
    history = [
        {"code": "006400", "date": "2026-01-10", "prices": [200, 210, 206, 220, 216], "future_return_d5": 5.2},
        {"code": "006400", "date": "2026-02-15", "prices": [300, 280, 260, 250, 240], "future_return_d5": -3.1},
    ]
    results = find_similar_patterns(current, history, top_k=2)
    assert len(results) <= 2
    assert results[0]["similarity"] >= results[-1]["similarity"]
