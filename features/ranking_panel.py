import discord
from discord import app_commands
import asyncio
from datetime import datetime, timedelta, timezone
from core.common import is_owner
from core.database import get_connection

JST = timezone(timedelta(hours=9))
PANEL_TABLE = "ranking_panels"
active_panels = {}

# ===== DB 初期化 =====
def init_db():
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
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT message_id, title, description FROM {PANEL_TABLE} WHERE channel_id = ?", (str(channel_id),))
    r = cur.fetchone()
    conn.close()
    if not r:
        return None
    return {"message_id": r[0], "title": r[1], "description": r[2]}

def save_panel(channel_id, message_id, title, description):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
        REPLACE INTO {PANEL_TABLE} (channel_id, message_id, title, description, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (str(channel_id), str(message_id), title, description))
    conn.commit()
    conn.close()

def get_ranking(limit=10):
    """ポイントの多い順に取得"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, points FROM point_users
        ORDER BY points DESC LIMIT ?
    """, (limit,))
    result = cur.fetchall()
    conn.close()
    return result

def get_user_rank_and_points(user_id):
    """指定ユーザーの順位とポイントを取得"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id, points FROM point_users ORDER BY points DESC")
    rows = cur.fetchall()
    conn.close()
    for idx, (uid, pts) in enumerate(rows, 1):
        if uid == str(user_id):
            return idx, pts
    return len(rows) if rows else 0, 0

# ===== ランキング埋め込み作成 =====
def build_ranking_embed(title, description, guild: discord.Guild):
    ranking = get_ranking(10)
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for idx, (uid, pts) in enumerate(ranking, 1):
        user = guild.get_member(int(uid))
        name = user.mention if user else f"ユーザーID:{uid}"
        prefix = medals[idx-1] if idx <= 3 else f" {idx}."
        lines.append(f"{prefix} {name} ・・・ **{pts:,}P**")
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

# ===== 編集モーダル =====
class RankingEditModal(discord.ui.Modal, title="ランキングパネル編集"):
    def __init__(self, current_title, current_desc):
        super().__init__(timeout=None)
        self._title = current_title
        self._desc = current_desc

    title_in = discord.ui.TextInput(
        label="パネルタイトル",
        default="🏆 ポイントランキング",
        required=True
    )
    desc_in = discord.ui.TextInput(
        label="説明文",
        default="現在のポイント上位10名を表示します✨",
        style=discord.TextStyle.long,
        required=True
    )

    async def on_submit(self, itx: discord.Interaction):
        await itx.response.defer()
        panel_data = get_panel(itx.channel_id)
        if not panel_data:
            await itx.followup.send("❌ パネル情報が見つかりません", ephemeral=True)
            return
        embed = build_ranking_embed(str(self.title_in), str(self.desc_in), itx.guild)
        try:
            msg = await itx.channel.fetch_message(panel_data["message_id"])
            await msg.edit(embed=embed)
            save_panel(itx.channel_id, panel_data["message_id"], str(self.title_in), str(self.desc_in))
            await itx.followup.send("✅ パネルを更新しました", ephemeral=True)
        except Exception as e:
            await itx.followup.send(f"❌ 更新に失敗: {e}", ephemeral=True)

# ===== View =====
class RankingPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="✏️ 内容編集",
        style=discord.ButtonStyle.secondary,
        custom_id="ranking:edit"
    )
    async def edit_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return
        panel_data = get_panel(itx.channel_id)
        if not panel_data:
            await itx.response.send_message("❌ 先にパネルを設置してください", ephemeral=True)
            return
        await itx.response.send_modal(RankingEditModal(panel_data["title"], panel_data["description"]))

    @discord.ui.button(
        label="🔄 今すぐ更新",
        style=discord.ButtonStyle.primary,
        custom_id="ranking:refresh"
    )
    async def refresh_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        await itx.response.defer(ephemeral=True)
        panel_data = get_panel(itx.channel_id)
        if not panel_data:
            await itx.followup.send("❌ パネル情報が見つかりません", ephemeral=True)
            return
        embed = build_ranking_embed(panel_data["title"], panel_data["description"], itx.guild)
        try:
            msg = await itx.channel.fetch_message(panel_data["message_id"])
            await msg.edit(embed=embed)
            await itx.followup.send("✅ 最新に更新しました", ephemeral=True)
        except Exception as e:
            await itx.followup.send(f"❌ 更新に失敗: {e}", ephemeral=True)

# ===== 自動更新タスク =====
async def auto_update_task(client: discord.Client):
    while True:
        now = datetime.now(JST)
        # 毎日23:59に実行
        target = now.replace(hour=23, minute=59, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait = (target - datetime.now(JST)).total_seconds()
        await asyncio.sleep(wait)
        # 全パネル更新
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT channel_id, message_id, title, description FROM {PANEL_TABLE}")
        panels = cur.fetchall()
        conn.close()
        for ch_id, msg_id, title, desc in panels:
            try:
                channel = client.get_channel(int(ch_id))
                if not channel:
                    continue
                embed = build_ranking_embed(title, desc, channel.guild)
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed)
            except Exception as e:
                print(f"⚠️ ランキング自動更新エラー: {e}")
        # 1分待機して次の日へ
        await asyncio.sleep(60)

# ===== セットアップ =====
async def setup_panel(channel):
    title = "🏆 ポイントランキング"
    desc = "現在のポイント上位10名を表示します✨"
    embed = build_ranking_embed(title, desc, channel.guild)
    view = RankingPanelView()
    msg = await channel.send(embed=embed, view=view)
    save_panel(channel.id, msg.id, title, desc)

async def setup(tree: app_commands.CommandTree):
    init_db()
    @tree.command(name="ポイントランキングパネル設置", description="ポイントランキングパネルを設置（オーナー専用）")
    async def cmd(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用コマンドです", ephemeral=True)
            return
        await setup_panel(itx.channel)
        await itx.response.send_message("✅ ランキングパネルを設置しました", ephemeral=True)
