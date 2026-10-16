import discord
from discord import app_commands
import json
import os
from datetime import datetime, timedelta, timezone
from core.common import is_owner

# ========== 全機能共通：データパス ==========
DATA_FILE = "kn_points_data.json"
JST = timezone(timedelta(hours=9))

# ========== 共通読み込み：lottery_panelと完全同一 ==========
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

def get_user_name(client, user_id):
    user = client.get_user(user_id)
    return user.display_name if user else f"ユーザー{user_id}"

# ========== パネル本体 ==========
class PointGivePanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="💳 ポイントを付与する",
        style=discord.ButtonStyle.primary,
        custom_id="point_give:open_modal"
    )
    async def give_btn(self, itx: discord.Interaction, btn):
        if is_owner(itx):
            await itx.response.send_modal(GivePointModal())
        else:
            await itx.response.send_modal(GivePointToMeModal(user_id=str(itx.user.id)))

class GivePointModal(discord.ui.Modal, title="💳 ポイント付与（管理者用）"):
    target_id = discord.ui.TextInput(
        label="付与先ユーザーID",
        placeholder="数字のIDを入力",
        required=True
    )
    amount = discord.ui.TextInput(
        label="付与するポイント数",
        placeholder="例: 100",
        required=True
    )

    async def on_submit(self, itx: discord.Interaction):
        try:
            uid = str(self.target_id.value.strip())
            amount = int(self.amount.value.strip())
        except ValueError:
            await itx.response.send_message("❌ 数値が正しくありません", ephemeral=True)
            return

        new_total = add_points(uid, amount)
        name = get_user_name(itx.client, uid)
        await itx.response.send_message(
            f"✅ **{name}** に {amount:,} ポイント付与しました✨\n"
            f"💳 合計：{new_total:,} ポイント（共通）",
            ephemeral=True
        )

class GivePointToMeModal(discord.ui.Modal, title="💳 自分にポイント付与"):
    amount = discord.ui.TextInput(
        label="付与するポイント数",
        placeholder="例: 10",
        required=True
    )
    def __init__(self, user_id):
        super().__init__()
        self._user_id = user_id

    async def on_submit(self, itx: discord.Interaction):
        try:
            amount = int(self.amount.value.strip())
        except ValueError:
            await itx.response.send_message("❌ 数値が正しくありません", ephemeral=True)
            return

        new_total = add_points(self._user_id, amount)
        await itx.response.send_message(
            f"✅ 自分に {amount:,} ポイント付与しました✨\n"
            f"💳 合計：{new_total:,} ポイント（共通）",
            ephemeral=True
        )

async def setup(tree: app_commands.CommandTree, bot=None):
    if bot is not None and not hasattr(bot, "_point_give_panel_registered"):
        bot.add_view(PointGivePanelView())
        bot._point_give_panel_registered = True
        print("✅ point_give_panel 永続View登録完了")

    @tree.command(name="ポイント付与パネル設置", description="ポイント付与パネルを設置")
    async def cmd(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用コマンドです", ephemeral=True)
            return
        embed = discord.Embed(
            title="💳 ポイント付与パネル",
            description=(
                "✅ **オーナー** → 任意のユーザーを指定可能\n"
                "✅ **一般ユーザー** → 自分自身にのみ付与\n"
                "📊 ポイントは全機能共通ですべて同じ値が反映されます\n"
                "下のボタンを押してポイントを追加してください✨"
            ),
            color=0x3498DB
        )
        await itx.response.send_message(embed=embed, view=PointGivePanelView())
        await itx.followup.send("✅ パネル設置完了", ephemeral=True)
