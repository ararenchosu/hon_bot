import sqlite3
import os

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DB_DIR, "kn_server.db")

def init_stats():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # ゲーム全体のプレイ回数を記録
    cur.execute("""CREATE TABLE IF NOT EXISTS game_stats (
        game_key TEXT PRIMARY KEY,
        play_count INTEGER DEFAULT 0
    )""")
    conn.commit()
    conn.close()

def increment(game_key: str) -> int:
    """ゲームキーごとに回数を+1して現在の値を返す（ユーザーに関係なく全体でカウント）"""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 存在しない場合は0で作成、存在する場合は+1
    cur.execute("""
        INSERT OR IGNORE INTO game_stats (game_key, play_count) VALUES (?, 0)
    """, (game_key,))
    cur.execute("""
        UPDATE game_stats SET play_count = play_count + 1 WHERE game_key = ?
    """, (game_key,))
    cur.execute("SELECT play_count FROM game_stats WHERE game_key = ?", (game_key,))
    row = cur.fetchone()
    conn.commit()
    conn.close()
    return row[0] if row else 1

def get_count(game_key: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT play_count FROM game_stats WHERE game_key = ?", (game_key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0
