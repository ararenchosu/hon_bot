from datetime import datetime, timedelta, timezone
import discord

# ========== サーバー固有設定 ==========
OWNER_ID = 1256574550901133377
CALL_CHANNEL_ID = 1558080580112089198
WELCOME_LEAVE_CHANNEL_ID = 1542788842078216297

# ========== 共通定数 ==========
JST = timezone(timedelta(hours=9))

# ========== 共通関数 ==========
def is_owner(itx):
    return itx.user.id == OWNER_ID

def format_account_age(dt):
    now = datetime.now(JST)
    delta = now - dt
    days = delta.days
    if days < 30:
        return f"{days}日"
    months = days // 30
    if months < 12:
        return f"{months}ヶ月"
    return f"{months // 12}年"
