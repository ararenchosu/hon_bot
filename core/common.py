# ========== サーバー固有設定 ==========
# オーナーを複数設定可能
OWNER_IDS = [
    1256574550901133377,   # メインオーナー
    1546348374922625065,   # 追加オーナー
]

CALL_CHANNEL_ID = 1558080580112089198          # 呼び出し通知用
WELCOME_LEAVE_CHANNEL_ID = 1542788842078216297 # 入退出通知用

# ========== 共通判定関数 ==========
def is_owner(interaction):
    """実行者がオーナーか判定"""
    return interaction.user.id in OWNER_IDS
