import discord
from discord import app_commands
import json
import os
from datetime import datetime, timedelta, timezone
from core.common import is_owner

JST = timezone(timedelta(hours=9))
DATA_FILE = "kn_points_data.json"

# ========== くじ引き基準で読み書き ==========
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}, {}, {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # ユーザーID:ポイント値 を抽出
        points = {}
        last_draw = data.get("last_lottery_draw", {})
        last_bonus = data.get("last_bonus_receive", {})
        for k, v in data.items():
            if k not in ["last_lottery_draw", "last_bonus_receive"]:
                points[k] = v
        return points, last_draw, last_bonus
    except Exception as e:
        print(f"⚠️ データ読み込みエラー: {e}")
        return {}, {}, {}

def save_data(points, last_draw, last_bonus):
    output = dict(points)
    output["last_lottery_draw"] = last_draw
    output["last_bonus_receive"] = last_bonus
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

def get_points(user_id: int):
    pts, _, _ = load_data()
    return pts.get(str(user_id), 0)

def add_points(user_id: int, amount: int):
    pts, last_draw, last_bonus = load_data()
    uid = str(user_id)
    pts[uid] = pts.get(uid, 0) + amount
    save_data(pts, last_draw, last_bonus)
    return pts[uid]

def set_points(user_id: int, amount: int):
    pts, last_draw, last_bonus = load_data()
    pts[str(user_id)] = amount
    save_data(pts, last_draw, last_bonus)

# ========== View ==========
class PointAdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="➕ ポイントを付与",
        style=discord.ButtonStyle.success,
        row=0,
        custom_id="admin:add"
    )
    async def add_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return
        class AddModal(discord.ui.Modal, title="ポイント付与"):
            user_id_input = discord.ui.TextInput(label="ユーザーID", required=True)
            amount_input = discord.ui.TextInput(label="付与するポイント数", required=True)
            async def on_submit(self, m_itx: discord.Interaction):
                await m_itx.response.defer(ephemeral=True)
                try:
                    uid = self.user_id_input.value.strip()
                    amount = int(self.amount_input.value.strip())
                except:
                    await m_itx.followup.send("❌ 数値を正しく入力してください", ephemeral=True)
                    return
                add_points(uid, amount)
                await m_itx.followup.send(f"✅ {uid} に {amount} ポイント付与しました", ephemeral=True)
        await itx.response.send_modal(AddModal())

    @discord.ui.button(
        label="➖ ポイントを減算",
        style=discord.ButtonStyle.danger,
        row=0,
        custom_id="admin:sub"
    )
    async def sub_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return
        class SubModal(discord.ui.Modal, title="ポイント減算"):
            user_id_input = discord.ui.TextInput(label="ユーザーID", required=True)
            amount_input = discord.ui.TextInput(label="減算するポイント数", required=True)
            async def on_submit(self, m_itx: discord.Interaction):
                await m_itx.response.defer(ephemeral=True)
                try:
                    uid = self.user_id_input.value.strip()
                    amount = int(self.amount_input.value.strip())
                except:
                    await m_itx.followup.send("❌ 数値を正しく入力してください", ephemeral=True)
                    return
                current = get_points(uid)
                set_points(uid, max(0, current - amount))
                await m_itx.followup.send(f"✅ {uid} から {amount} ポイント減算しました", ephemeral=True)
        await itx.response.send_modal(SubModal())

    @discord.ui.button(
        label="🔢 ポイントを設定",
        style=discord.ButtonStyle.primary,
        row=1,
        custom_id="admin:set"
    )
    async def set_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return
        class SetModal(discord.ui.Modal, title="ポイント設定"):
            user_id_input = discord.ui.TextInput(label="ユーザーID", required=True)
            amount_input = discord.ui.TextInput(label="設定するポイント数", required=True)
            async def on_submit(self, m_itx: discord.Interaction):
                await m_itx.response.defer(ephemeral=True)
                try:
                    uid = self.user_id_input.value.strip()
                    amount = int(self.amount_input.value.strip())
                except:
                    await m_itx.followup.send("❌ 数値を正しく入力してください", ephemeral=True)
                    return
                set_points(uid, amount)
                await m_itx.followup.send(f"✅ {uid} のポイントを {amount} に設定しました", ephemeral=True)
        await itx.response.send_modal(SetModal())

    @discord.ui.button(
        label="📊 ポイント確認",
        style=discord.ButtonStyle.secondary,
        row=1,
        custom_id="admin:check"
    )
    async def check_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return
        class CheckModal(discord.ui.Modal, title="ポイント確認"):
            user_id_input = discord.ui.TextInput(label="確認するユーザーID", required=True)
            async def on_submit(self, m_itx: discord.Interaction):
                await m_itx.response.defer(ephemeral=True)
                uid = self.user_id_input.value.strip()
                pts = get_points(uid)
                await m_itx.followup.send(f"💳 {uid} のポイント：{pts}", ephemeral=True)
        await itx.response.send_modal(CheckModal())

async def setup(tree, bot=None):
    if bot is not None and not hasattr(bot, "_point_admin_registered"):
        bot.add_view(PointAdminView())
        bot._point_admin_registered = True
        print("✅ point_admin_panel 永続View登録完了")

    @tree.command(name="管理ポイントパネル", description="ポイント管理パネル（オーナー専用）")
    async def cmd(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用コマンドです", ephemeral=True)
            return
        embed = discord.Embed(title="💰 ポイント管理", color=0xF1C40F)
        embed.description = "各ボタンからポイントの操作ができます✨"
        await itx.response.send_message(embed=embed, view=PointAdminView())
