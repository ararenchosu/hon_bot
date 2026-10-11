import discord
from discord import app_commands
import random
import json
import os
from datetime import datetime, timedelta, timezone
from core.common import is_owner

# ===== 統計用共通モジュール読み込み =====
from core.game_stats import increment

JST = timezone(timedelta(hours=9))
DATA_FILE = "kn_points_data.json"
SLOT_RESULT_CHANNEL_ID = 1558766953114370158  # チャンネルID

SYMBOLS = ["🍒", "🍋", "🔔", "💎", "7️⃣"]
PAYOUT = {
    ("💎", "💎", "💎"): 10,
    ("7️⃣", "7️⃣", "7️⃣"): 7,
    ("🔔", "🔔", "🔔"): 5,
    ("🍋", "🍋", "🍋"): 3,
    ("🍒", "🍒", "🍒"): 2,
    ("🍒", "🍒"): 1,
}

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"points": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"points": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_points(user_id):
    return load_data().get("points", {}).get(str(user_id), 0)

def add_points(user_id, amount):
    data = load_data()
    uid = str(user_id)
    data["points"][uid] = data["points"].get(uid, 0) + amount
    save_data(data)
    return data["points"][uid]

def spin_slot():
    return [random.choice(SYMBOLS) for _ in range(3)]

def calc_payout(reels, bet):
    triple = tuple(reels)
    if triple in PAYOUT:
        return bet * PAYOUT[triple], f"✨ {PAYOUT[triple]}倍！"
    if tuple(reels[:2]) in PAYOUT:
        return bet * PAYOUT[tuple(reels[:2])], f"🍒🍒 {PAYOUT[tuple(reels[:2])]}倍"
    return -bet, "💔 ハズレ"

async def send_result_embed(client, user, reels, result_text, change, total, bet):
    channel = client.get_channel(SLOT_RESULT_CHANNEL_ID)
    if not channel:
        print(f"⚠️ 結果チャンネルが見つかりません: {SLOT_RESULT_CHANNEL_ID}")
        return

    embed = discord.Embed(
        title="🎰 スロット結果",
        description=f"{user.mention} がスロットを回しました！",
        color=0xFFD700 if change >= 0 else 0x666666,
        timestamp=datetime.now(JST)
    )
    embed.add_field(name="絵柄", value=f"{reels[0]} | {reels[1]} | {reels[2]}", inline=False)
    embed.add_field(name="結果", value=result_text, inline=True)
    if bet > 0:
        embed.add_field(name="賭けP", value=f"{bet}P", inline=True)
    embed.add_field(name="変動", value=f"{change:+d}P", inline=True)
    embed.add_field(name="合計P", value=f"{total}P", inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    await channel.send(embed=embed)

    # ===== チャンネル名更新 =====
    count = increment("slot")
    if channel:
        await channel.edit(name=f"🎰・スロット・{count}回", reason="プレイ回数更新")


class SlotPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="💳 ポイント確認",
        style=discord.ButtonStyle.success,
        custom_id="slot:check_points",
        row=0
    )
    async def check_points_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        pts = get_points(itx.user.id)
        await itx.response.send_message(
            f"💳 {itx.user.mention} が現在持っているポイントは **{pts}P** です✨",
            ephemeral=True
        )

    @discord.ui.button(
        label="🎰 掛けなしスロット",
        style=discord.ButtonStyle.secondary,
        custom_id="slot:free",
        row=1
    )
    async def free_slot(self, itx: discord.Interaction, btn: discord.ui.Button):
        reels = spin_slot()
        result_text = "🍀 お試し回転！"
        await itx.response.send_message(
            f"🎰 {reels[0]} | {reels[1]} | {reels[2]}\n{result_text}",
            ephemeral=True
        )
        await send_result_embed(itx.client, itx.user, reels, result_text, 0, get_points(itx.user.id), 0)

    @discord.ui.button(
        label="🎰 10P スロット",
        style=discord.ButtonStyle.primary,
        custom_id="slot:bet10",
        row=2
    )
    async def bet10_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        await play_slot(itx, 10)

    @discord.ui.button(
        label="🎰 50P スロット",
        style=discord.ButtonStyle.primary,
        custom_id="slot:bet50",
        row=2
    )
    async def bet50_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        await play_slot(itx, 50)

    @discord.ui.button(
        label="🎰 100P スロット",
        style=discord.ButtonStyle.danger,
        custom_id="slot:bet100",
        row=2
    )
    async def bet100_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        await play_slot(itx, 100)


async def play_slot(itx, bet):
    pts = get_points(itx.user.id)
    if pts < bet:
        await itx.response.send_message(
            f"❌ ポイントが足りません！（所持：{pts}P / 必要：{bet}P）",
            ephemeral=True
        )
        return
    reels = spin_slot()
    gain, result_text = calc_payout(reels, bet)
    new_total = add_points(itx.user.id, gain)
    await itx.response.send_message(
        f"🎰 {reels[0]} | {reels[1]} | {reels[2]}\n"
        f"{result_text}\n"
        f"💳 合計：{new_total}P",
        ephemeral=True
    )
    await send_result_embed(itx.client, itx.user, reels, result_text, gain, new_total, bet)


async def setup(tree: app_commands.CommandTree):
    @tree.command(name="スロットパネル設置", description="スロットパネルを設置（オーナー専用）")
    async def cmd(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return
        embed = discord.Embed(
            title="🎰 スロットマシン",
            description=(
                "💳 **ポイント確認** → 現在の所持ポイントを表示\n"
                "🍀 **掛けなし** → 結果だけ楽しむ\n"
                "💰 **掛けあり** → 当たればポイント増！\n"
                "💎💎💎：10倍 / 7️⃣7️⃣7️⃣：7倍 / 🔔🔔🔔：5倍\n"
                "🍋🍋🍋：3倍 / 🍒🍒🍒：2倍 / 🍒🍒：1倍"
            ),
            color=0xFFD700
        )
        await itx.response.send_message(embed=embed, view=SlotPanelView())
        await itx.followup.send("✅ スロットパネル設置完了", ephemeral=True)
