# ========== サーバー固有設定 ==========
OWNER_IDS = [
    1256574550901133377,   # メインオーナー
    1546348374922625065,   # 追加オーナー
]

CALL_CHANNEL_ID = 1558080580112089198
WELCOME_LEAVE_CHANNEL_ID = 1542788842078216297
RESULT_CHANNEL_ID = 1558468434596077661  # ← 追加

from datetime import timezone, timedelta
JST = timezone(timedelta(hours=9), "JST")

# ========== 共通判定関数 ==========
def is_owner(interaction):
    return interaction.user.id in OWNER_IDS
