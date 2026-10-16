import discord
from datetime import datetime, timedelta, timezone
from core.common import is_owner
import os
import json

JST = timezone(timedelta(hours=9))
DATA_FILE = "kn_points_data.json"
BONUS_POINTS = 10  # 1日のボーナスポイント

# ========== くじ引き基準 読み書き ==========
def load_all_data():
    if not os.path.exists(DATA_FILE):
        return {}, {}, {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        points = {}
        last_draw = data.get("last_lottery_draw", {})
        last_bonus = data.get("last_bonus_receive", {})
        for k, v in data.items():
            if k not in ["last_lottery_draw", "last_bonus_receive"]:
                points[k] = v
        return points, last_draw, last_bonus
    except Exception as e:
        print(f"⚠️ 読み込みエラー: {e}")
        return {}, {}, {}

def save_all_data(points, last_draw, last_bonus):
    output = dict(points)
    output["last_lottery_draw"] = last_draw
    output["last_bonus_receive"] = last_bonus
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

def get_points(user_id):
    pts, _, _ = load_all_data()
    return pts.get(str(user_id), 0)

def add_points(user_id, amount):
    pts, last_draw, last_bonus = load_all_data()
    uid = str(user_id)
    pts[uid] = pts.get(uid, 0) + amount
    save_all_data(pts, last_draw, last_bonus)
    return pts[uid]

def can_receive_bonus_today(user_id):
    _, _, last_bonus = load_all_data()
    today = datetime.now(JST).strftime("%Y-%m-%d")
    return last_bonus.get(str(user_id)) != today

def mark_bonus_received(user_id):
    pts, last_draw, last_bonus = load_all_data()
    last_bonus[str(user_id)] = datetime.now(JST).strftime("%Y-%m-%d")
    save_all_data(pts, last_draw, last_bonus)

# ========== View ==========
class LoginBonusView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🎁 ログインボーナス受け取り",
        style=discord.ButtonStyle.primary,
        custom_id="login_bonus:receive"
    )
    async def receive_btn(self, itx: discord.Interaction, btn):
        if not can_receive_bonus_today(itx.user.id):
            await itx.response.send_message(
                "❌ 今日は既に受け取っています。また明日お待ちください✨",
                ephemeral=True
            )
            return
        
        mark_bonus_received(itx.user.id)
        new_points = add_points(itx.user.id, BONUS_POINTS)
        await itx.response.send_message(
            f"🎁 ログインボーナス **{BONUS_POINTS}ポイント** 受け取り✨\n"
            f"💳 現在のポイント：**{new_points:,}ポイント**",
            ephemeral=True
        )

async def setup_panel(channel):
    embed = discord.Embed(
        title="🎁 1日1回ログインボーナス",
        description=f"下のボタンを押すと **{BONUS_POINTS}ポイント** 受け取れます✨\n毎日0:00にリセット",
        color=0x2ECC71
    )
    await channel.send(embed=embed, view=LoginBonusView())

async def setup(tree, bot=None):
    if bot is not None and not hasattr(bot, "_login_bonus_registered"):
        bot.add_view(LoginBonusView())
        bot._login_bonus_registered = True
        print("✅ login_bonus 永続View登録完了")

    @tree.command(name="ログインボーナスパネル設置", description="ログインボーナスパネル設置（オーナー専用）")
    async def cmd(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.defer(ephemeral=True)
        await setup_panel(itx.channel)
        await itx.followup.send("✅ 設置完了", ephemeral=True)
