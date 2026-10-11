import json
import os

STATS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "game_stats.json")

def _load():
    os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
    if not os.path.exists(STATS_FILE):
        return {}
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(data):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def increment(game_key: str) -> int:
    """回数を+1して新しい値を返す"""
    d = _load()
    d[game_key] = d.get(game_key, 0) + 1
    _save(d)
    return d[game_key]

def get(game_key: str) -> int:
    d = _load()
    return d.get(game_key, 0)
