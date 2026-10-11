import discord
from discord import app_commands
from core.common import is_owner
import json
import os
from datetime import datetime, timedelta, timezone
JST = timezone(timedelta(hours=9))

# ✅ 結果通知用チャンネルID
LOTTERY_RESULT_CHANNEL_ID = 1558705232781906071

DATA_FILE = "kn_points_data.json"

class PointData:
    def __init__(self):
        self.points = {}
        self.last_lottery_draw = {}   # くじ用 最終取得日
        self.last_bonus_receive = {}  # ボーナス用 最終取得日
        self._load()

    def _load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.points = data.get("points", {})
                    # 旧形式からの引き継ぎ
                    old_last = data.get("last_draw", {})
                    if not data.get("last_lottery_draw"):
                        self.last_lottery_draw = old_last
                    else:
                        self.last_lottery_draw = data.get("last_lottery_draw", {})
                    self.last_bonus_receive = data.get("last_bonus_receive", {})
            except Exception as e:
                print(f"⚠️ データ読み込みエラー: {e}")
                self.points = {}
                self.last_lottery_draw = {}
                self.last_bonus_receive = {}

    def _save(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "points": self.points,
                "last_lottery_draw": self.last_lottery_draw,
                "last_bonus_receive": self.last_bonus_receive
            }, f, ensure_ascii=False, indent=2)

    def get_points(self, user_id):
        return self.points.get(str(user_id), 0)

    def add_points(self, user_id, amount):
        uid = str(user_id)
        self.points[uid] = self.get_points(user_id) + amount
        self._save()
        return self.points[uid]

    # ✅ くじ用
    def can_lottery_today(self, user_id):
        today = datetime.now(JST).strftime("%Y-%m-%d")
        return self.last_lottery_draw.get(str(user_id)) != today

    def mark_lottery_drew(self, user_id):
        today = datetime.now(JST).strftime("%Y-%m-%d")
        self.last_lottery_draw[str(user_id)] = today
        self._save()

    # ✅ ボーナス用
    def can_receive_bonus_today(self, user_id):
        today = datetime.now(JST).strftime("%Y-%m-%d")
        return self.last_bonus_receive.get(str(user_id)) != today

    def mark_bonus_received(self, user_id):
        today = datetime.now(JST).strftime("%Y-%m-%d")
        self.last_bonus_receive[str(user_id)] = today
        self._save()

point_data = PointData()

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

    @discord.ui.button(label="🗳くじを引く！", style=discord.ButtonStyle.primary, custom_id="lottery:draw")
    async def draw_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not point_data.can_lottery_today(itx.user.id):
            await itx.response.send_message(
                "❌ 今日は既にくじを引いています。また明日お試しください！",
                ephemeral=True
            )
            return

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

        point_data.mark_lottery_drew(itx.user.id)
        new_points = point_data.add_points(itx.user.id, prize["points"])

        # ✅ 結果をユーザーに返信
        await itx.response.send_message(
            f"🎉 {prize['name']} 当選！\n"
            f"➕ {prize['points']}ポイント 獲得✨\n"
            f"💳 現在のポイント：{new_points}ポイント",
            ephemeral=True
        )

        # ✅ 結果を指定チャンネルに送信
        await send_lottery_result_embed(itx, prize, new_points)

    # ✅ オーナー専用テストボタン
    @discord.ui.button(label="🧪 通知テスト(オーナーのみ)", style=discord.ButtonStyle.secondary, custom_id="lottery:test", row=1)
    async def test_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ このボタンはオーナー専用です", ephemeral=True)
            return

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

        # ✅ テスト用：ポイント加算も日付記録もしない
        dummy_points = point_data.get_points(itx.user.id)  # 現在のポイントをそのまま表示
        await itx.response.send_message(
            f"🧪 テスト実行！\n"
            f"表示結果：{prize['name']}\n"
            f"⚠️ ポイント・抽選権には影響しません",
            ephemeral=True
        )

        # ✅ 通知だけ送信
        await send_lottery_result_embed(itx, prize, dummy_points, is_test=True)

    @discord.ui.button(label="✏️ パネル編集", style=discord.ButtonStyle.secondary, custom_id="lottery:edit", row=2)
    async def edit_lottery_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return
        class LotteryEditModal(discord.ui.Modal, title="くじパネル編集"):
            title_in = discord.ui.TextInput(
                label="タイトル",
                default="🗳1日1回！くじ引き",
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


# ✅ 通知送信を共通化した関数
async def send_lottery_result_embed(itx, prize, total_points, is_test=False):
    result_channel = itx.client.get_channel(LOTTERY_RESULT_CHANNEL_ID)
    if not result_channel:
        print(f"⚠️ 結果通知チャンネルが見つかりません: {LOTTERY_RESULT_CHANNEL_ID}")
        return

    title = "🧪 【テスト】くじ引き結果" if is_test else "🗳 くじ引き結果"
    description = f"{itx.user.mention} がくじを引きました！"
    if is_test:
        description = f"{itx.user.mention} がテスト抽選を実行しました！\n⚠️ これはテストです（ポイント加算なし）"

    result_embed = discord.Embed(
        title=title,
        description=description,
        color=0x888888 if is_test else 0xFFD700,
        timestamp=datetime.now(JST)
    )
    result_embed.add_field(name="🎯 結果", value=prize["name"], inline=True)
    result_embed.add_field(name="✨ 獲得ポイント", value=f"{prize['points']}ポイント", inline=True)
    result_embed.add_field(name="💳 合計ポイント", value=f"{total_points}ポイント", inline=True)
    result_embed.set_thumbnail(url=itx.user.display_avatar.url)

    await result_channel.send(embed=result_embed)


class PointCheckPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💳 ポイントを確認", style=discord.ButtonStyle.success, custom_id="points:check")
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
            title="🗳1日1回！くじ引き",
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
