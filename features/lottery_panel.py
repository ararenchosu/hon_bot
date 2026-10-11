import discord
from discord import app_commands
from core.common import is_owner
import json
import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

# ✅ データ保存先ファイル
DATA_FILE = "kn_points_data.json"

# ✅ データ読み書きクラス
class PointData:
    def __init__(self):
        self.points = {}       # {ユーザーID: ポイント数}
        self.last_draw = {}    # {ユーザーID: "YYYY-MM-DD" 最後に引いた日付}
        self._load()

    def _load(self):
        """ファイルから読み込み"""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.points = data.get("points", {})
                    self.last_draw = data.get("last_draw", {})
            except Exception as e:
                print(f"⚠️ データ読み込みエラー: {e}")
                self.points = {}
                self.last_draw = {}

    def _save(self):
        """ファイルに保存"""
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "points": self.points,
                "last_draw": self.last_draw
            }, f, ensure_ascii=False, indent=2)

    def get_points(self, user_id):
        return self.points.get(str(user_id), 0)

    def add_points(self, user_id, amount):
        uid = str(user_id)
        self.points[uid] = self.get_points(user_id) + amount
        self._save()
        return self.points[uid]

    def can_draw_today(self, user_id):
        today = datetime.now(JST).strftime("%Y-%m-%d")
        return self.last_draw.get(str(user_id)) != today

    def mark_drew_today(self, user_id):
        today = datetime.now(JST).strftime("%Y-%m-%d")
        self.last_draw[str(user_id)] = today
        self._save()

# ✅ グローバルインスタンス（起動時に自動読み込み）
point_data = PointData()

# ✅ くじの設定
LOTTERY_PRIZES = [
    {"name": "🎖️ 1等", "points": 100, "rate": 0.05},
    {"name": "🥈 2等", "points": 75,  "rate": 0.10},
    {"name": "🥉 3等", "points": 50,  "rate": 0.20},
    {"name": "🏅 4等", "points": 25,  "rate": 0.30},
    {"name": "🎀 5等", "points": 10,  "rate": 0.35},
]


class LotteryPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎰 くじを引く！", style=discord.ButtonStyle.primary, custom_id="lottery:draw")
    async def draw_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not point_data.can_draw_today(itx.user.id):
            await itx.response.send_message(
                "❌ 今日は既に引いています。また明日お試しください！",
                ephemeral=True
            )
            return

        # ✅ 確率に基づいて当選を決定
        import random
        r = random.random()
        cumulative = 0
        prize = None
        for p in LOTTERY_PRIZES:
            cumulative += p["rate"]
            if r < cumulative:
                prize = p
                break
        if prize is None:
            prize = LOTTERY_PRIZES[-1]

        # ✅ ポイント付与＆記録
        point_data.mark_drew_today(itx.user.id)
        new_points = point_data.add_points(itx.user.id, prize["points"])

        await itx.response.send_message(
            f"🎉 {prize['name']} 当選！\n"
            f"➕ {prize['points']}ポイント 獲得✨\n"
            f"💳 現在のポイント：{new_points}ポイント",
            ephemeral=True
        )

    @discord.ui.button(label="✏️ パネル編集", style=discord.ButtonStyle.secondary, custom_id="lottery:edit")
    async def edit_lottery_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return

        class LotteryEditModal(discord.ui.Modal, title="くじパネル編集"):
            title_in = discord.ui.TextInput(
                label="タイトル",
                default="🗳️1日1回！くじ引き",
                required=True
            )
            desc_in = discord.ui.TextInput(
                label="説明文",
                style=discord.TextStyle.long,
                default="⬇️のボタンを押して1日1回くじが引けます✨\n"
                        "🎖️1等:100pt / 🥈2等:75pt / 🥉3等:50pt / 🏅4等:25pt / 🎀5等:10pt",
                required=True
            )
            async def on_submit(self, m_itx: discord.Interaction):
                embed = discord.Embed(
                    title=str(self.title_in),
                    description=str(self.desc_in),
                    color=0xFFD700
                )
                await m_itx.response.edit_message(embed=embed, view=LotteryPanelView())
                await m_itx.followup.send("✅ くじパネルを更新しました", ephemeral=True)

        await itx.response.send_modal(LotteryEditModal())


class PointCheckPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💰ポイントを確認", style=discord.ButtonStyle.success, custom_id="points:check")
    async def check_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        pts = point_data.get_points(itx.user.id)
        await itx.response.send_message(
            f"💳 {itx.user.mention} が現在持っているポイントは **{pts}ポイント** です✨",
            ephemeral=True
        )

    @discord.ui.button(label="✏️ パネル編集", style=discord.ButtonStyle.secondary, custom_id="points:edit")
    async def edit_point_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return

        class PointEditModal(discord.ui.Modal, title="ポイントパネル編集"):
            title_in = discord.ui.TextInput(
                label="タイトル",
                default="💰ポイント確認",
                required=True
            )
            desc_in = discord.ui.TextInput(
                label="説明文",
                style=discord.TextStyle.long,
                default="⬇️のボタンを押すと現在のポイントが確認できます✨",
                required=True
            )
            async def on_submit(self, m_itx: discord.Interaction):
                embed = discord.Embed(
                    title=str(self.title_in),
                    description=str(self.desc_in),
                    color=0x2ECC71
                )
                await m_itx.response.edit_message(embed=embed, view=PointCheckPanelView())
                await m_itx.followup.send("✅ ポイントパネルを更新しました", ephemeral=True)

        await itx.response.send_modal(PointEditModal())


async def setup(tree):
    @tree.command(name="くじ引きパネル設置", description="くじ引きパネルを設置（オーナー専用）")
    async def cmd_lottery_panel(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用コマンドです", ephemeral=True)
            return
        embed = discord.Embed(
            title="🗳️1日1回！くじ引き",
            description="⬇️のボタンを押して1日1回くじが引けます✨\n"
                        "🎖️1等:100pt / 🥈2等:75pt / 🥉3等:50pt / 🏅4等:25pt / 🎀5等:10pt",
            color=0xFFD700
        )
        await itx.response.send_message(embed=embed, view=LotteryPanelView())

    @tree.command(name="ポイント確認パネル設置", description="ポイント確認パネルを設置（オーナー専用）")
    async def cmd_point_panel(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用コマンドです", ephemeral=True)
            return
        embed = discord.Embed(
            title="💰ポイント確認",
            description="⬇️のボタンを押すと現在のポイントが確認できます✨",
            color=0x2ECC71
        )
        await itx.response.send_message(embed=embed, view=PointCheckPanelView())
