import sqlite3
import os

# データ保存先：dataフォルダに入れる
DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DB_DIR, "kn_server.db")

def init_db():
    # dataフォルダがなければ作成
    os.makedirs(DB_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 認証設定
    cur.execute("""CREATE TABLE IF NOT EXISTS auth_setting (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    cur.execute("INSERT OR IGNORE INTO auth_setting VALUES ('default_role', '鯖メン')")
    
    # 選択式ロール一覧
    cur.execute("""CREATE TABLE IF NOT EXISTS select_roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT,
        role_id TEXT,
        role_name TEXT
    )""")
    
    # 各種設定
    cur.execute("""CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    cur.execute("INSERT OR IGNORE INTO config VALUES ('call_message', '$caller$さんが $target$さんを呼んでいます。')")
    
    # メンバー番号管理
    cur.execute("""CREATE TABLE IF NOT EXISTS stats (
        key TEXT PRIMARY KEY,
        value INTEGER
    )""")
    cur.execute("INSERT OR IGNORE INTO stats VALUES ('member_total', 0)")
    
    conn.commit()
    conn.close()
    print("✅ データベース準備完了（永続保存）")

def get_connection():
    """どのファイルからもこれを使ってDBに接続する"""
    return sqlite3.connect(DB_PATH)
