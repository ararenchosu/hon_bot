import discord
from discord import app_commands
import json
import os
from datetime import datetime, timedelta, timezone
from core.common import is_owner

JST = timezone(timedelta(hours=9))
DATA_FILE = "kn_points_data.json"

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

def set_points(user_id, amount):
    data = load_data()
    uid = str(user_id)
    data["points"][uid] = amount
    save_data(data)
    return data["points"][uid]

def add_points(user_id, amount):
    data = load_data()
    uid = str(user_id)
    data["points"][uid] = data["points"].get(uid, 0) + amount
    save_data(data)
    return data["points"][uid]

# === ポイント付与用モーダル ===
class AddPointsModal(discord.ui.Modal, title="➕ ポイントを付与"):
    amount = discord.ui.TextInput(
        label="付与する数（マイナス可）",
        placeholder="例：100 / -50",
        required=True
    )

    def __init__(self, target_user):
        super().__init__()
        self.target_user = target_user

    async def on_submit(self, itx: discord.Interaction):
        try:
            val = int(self.amount.value)
        except ValueError:
            await itx.response.send_message("❌ 数字を入力してください", ephemeral=True)
            return
        new_total = add_points(self.target_user.id, val)
        embed = discord.Embed(
            title="✅ ポイント付与完了",
            description=f"{self.target_user.mention}\n{val:+d}P → **{new_total}P**",
            color=0x2ECC71, timestamp=datetime.now(JST)
        )
        embed.set_thumbnail(url=self.target_user.display_avatar.url)
        await itx.response.send_message(embed=embed, ephemeral=True)

# === ポイント設定用モーダル ===
class SetPointsModal(discord.ui.Modal, title="✏️ ポイントを設定"):
    amount = discord.ui.TextInput(
        label="設定する数",
        placeholder="例：500",
        required=True
    )

    def __init__(self, target_user):
        super().__init__()
        self.target_user = target_user

    async def on_submit(self, itx: discord.Interaction):
        try:
            val = int(self.amount.value)
        except ValueError:
            await itx.response.send_message("❌ 数字を入力してください", ephemeral=True)
            return
        new_total = set_points(self.target_user.id, val)
        embed = discord.Embed(
            title="✅ ポイント設定完了",
            description=f"{self.target_user.mention}\n**{new_total}P** に設定",
            color=0x3498DB, timestamp=datetime.now(JST)
        )
        embed.set_thumbnail(url=self.target_user.display_avatar.url)
        await itx.response.send_message(embed=embed, ephemeral=True)

# === ユーザー選択ビュー ===
class SelectUserView(discord.ui.View):
    def __init__(self, action):
        super().__init__(timeout=120)
        self.action = action
        # 選択メニューを動的に追加
        self.add_item(
            discord.ui.UserSelect(
                custom_id="select_user",
                placeholder="ユーザーを選択してください"
            )
        )

    async def interaction_check(self, itx: discord.Interaction) -> bool:
        selected_user = itx.data["values"][0]
        user = await itx.client.fetch_user(int(selected_user))

        if self.action == "add":
            await itx.response.send_modal(AddPointsModal(user))
        elif self.action == "set":
            await itx.response.send_modal(SetPointsModal(user))
        elif self.action == "check":
            pts = get_points(user.id)
            embed = discord.Embed(
                title="💳 ポイント確認",
                description=f"{user.mention}：**{pts}P**",
                color=0xF1C40F, timestamp=datetime.now(JST)
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            await itx.response.send_message(embed=embed, ephemeral=True)
        elif self.action == "reset":
            set_points(user.id, 0)
            embed = discord.Embed(
                title="🗑️ リセット完了",
                description=f"{user.mention} を0Pにしました",
                color=0xE74C3C, timestamp=datetime.now(JST)
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            await itx.response.send_message(embed=embed, ephemeral=True)
        return True

# === メインパネル ===
class PointAdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="➕ ポイントを付与", style=discord.ButtonStyle.success, custom_id="point:add", row=0)
    async def add_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.send_message(
            "➕ 付与するユーザーを選択してください",
            view=SelectUserView("add"),
            ephemeral=True
        )

    @discord.ui.button(label="✏️ ポイントを設定", style=discord.ButtonStyle.primary, custom_id="point:set", row=0)
    async def set_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.send_message(
            "✏️ 設定するユーザーを選択してください",
            view=SelectUserView("set"),
            ephemeral=True
        )

    @discord.ui.button(label="💳 ポイント確認", style=discord.ButtonStyle.secondary, custom_id="point:check", row=1)
    async def check_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.send_message(
            "💳 確認するユーザーを選択してください",
            view=SelectUserView("check"),
            ephemeral=True
        )

    @discord.ui.button(label="🗑️ 0にリセット", style=discord.ButtonStyle.danger, custom_id="point:reset", row=1)
    async def reset_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.send_message(
            "🗑️ リセットするユーザーを選択してください",
            view=SelectUserView("reset"),
            ephemeral=True
        )

async def setup(tree: app_commands.CommandTree):
    @tree.command(name="ポイント付与パネル設置", description="ポイント管理パネル設置（オーナー専用）")
    async def cmd(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        embed = discord.Embed(
            title="💳 ポイント管理パネル",
            description="""➕ ポイントを付与 → 増減（マイナス可）
✏️ ポイントを設定 → 値を直接指定
💳 ポイント確認 → 現在の所持数を表示
🗑️ 0にリセット → 選択したユーザーを0Pに
🔒 オーナー以外は操作できません""",
            color=0xF1C40F, timestamp=datetime.now(JST)
        )
        await itx.response.send_message(embed=embed, view=PointAdminView())
        await itx.followup.send("✅ パネル設置完了", ephemeral=True)
