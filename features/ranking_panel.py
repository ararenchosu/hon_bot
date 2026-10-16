import discord
from discord import app_commands
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from core.common import is_owner

JST = timezone(timedelta(hours=9))
PANEL_TABLE = "ranking_panels"
DATA_FILE = "kn_points_data.json"

# ========== くじ引き基準で読み込み ==========
def load_points_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 管理キーを除外してユーザーデータだけ抽出
        pts = {}
        for k, v in data.items():
            if k not in ["last_lottery_draw", "last_bonus_receive"]:
                pts[k] = v
        return pts
    except Exception as e:
        print(f"⚠️ 読み込みエラー: {e}")
        return {}

# ========== DB処理 ==========
def init_db():
    from core.database import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {PANEL_TABLE} (
            channel_id TEXT PRIMARY KEY,
            message_id TEXT,
            title TEXT,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def get_panel(channel_id):
    from core.database import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT message_id, title, description FROM {PANEL_TABLE} WHERE channel_id = ?", (str(channel_id),))
    r = cur.fetchone()
    conn.close()
    if r:
        return {"message_id": r[0], "title": r[1], "description": r[2]}
    return None

def save_panel(channel_id, message_id, title, description):
    from core.database import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
        REPLACE INTO {PANEL_TABLE} (channel_id, message_id, title, description)
        VALUES (?, ?, ?, ?)
    """, (str(channel_id), str(message_id), title, description))
    conn.commit()
    conn.close()

# ========== ランキング作成 ==========
def get_ranking(limit=10):
    pts = load_points_data()
    return sorted(pts.items(), key=lambda x: x[1], reverse=True)[:limit]

def build_ranking_embed(title, description, guild):
    ranking = get_ranking(10)
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for idx, (uid, pts) in enumerate(ranking, 1):
        user = guild.get_member(int(uid))
        name = user.mention if user else f"ユーザー:{uid}"
        m = medals[idx-1] if idx <= 3 else f" {idx}."
        lines.append(f"{m} {name} ・・・ **{pts:,}P**")
    if not lines:
        lines.append("まだポイントが記録されていません")
    embed = discord.Embed(
        title=title,
        description=description + "\n\n" + "\n".join(lines),
        color=0xFFD700,
        timestamp=datetime.now(JST)
    )
    embed.set_footer(text=f"最終更新: {datetime.now(JST).strftime('%H:%M:%S')}")
    return embed

# ========== View ==========
class RankingPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔄 更新", style=discord.ButtonStyle.primary, custom_id="ranking:refresh")
    async def refresh_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        await itx.response.defer(ephemeral=True)
        panel = get_panel(itx.channel_id)
        if not panel:
            await itx.followup.send("❌ パネルが見つかりません", ephemeral=True)
            return
        embed = build_ranking_embed(panel["title"], panel["description"], itx.guild)
        msg = await itx.channel.fetch_message(panel["message_id"])
        await msg.edit(embed=embed)
        await itx.followup.send("✅ 更新しました", ephemeral=True)

async def setup_panel(channel):
    title = "🏆 ポイントランキング"
    desc = "上位10名のポイントです✨"
    embed = build_ranking_embed(title, desc, channel.guild)
    view = RankingPanelView()
    msg = await channel.send(embed=embed, view=view)
    save_panel(channel.id, msg.id, title, desc)

async def setup(tree, bot=None):
    init_db()
    if bot is not None and not hasattr(bot, "_ranking_registered"):
        bot.add_view(RankingPanelView())
        bot._ranking_registered = True
        print("✅ ranking_panel 永続View登録完了")

    @tree.command(name="ポイントランキングパネル設置", description="ランキングパネル設置")
    async def cmd(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.defer(ephemeral=True)
        await setup_panel(itx.channel)
        await itx.followup.send("✅ ランキングパネル設置完了", ephemeral=True)
