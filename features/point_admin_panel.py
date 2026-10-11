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

class PointAmountModal(discord.ui.Modal, title="ポイント数を入力"):
    amount_input = discord.ui.TextInput(
        label="付与するポイント数",
        placeholder="例: 100 または -50",
        required=True
    )

    def __init__(self, target_user):
        super().__init__()
        self.target_user = target_user

    async def on_submit(self, itx: discord.Interaction):
        try:
            amount = int(self.amount_input.value)
        except ValueError:
            await itx.response.send_message("❌ 数字を入力してください", ephemeral=True)
            return
        
        new_total = add_points(self.target_user.id, amount)
        
        embed = discord.Embed(
            title="✅ ポイント付与完了",
            description=f"{self.target_user.mention} に {amount:+d}P しました\n現在: **{new_total}P**",
            color=0x2ECC71,
            timestamp=datetime.now(JST)
        )
        embed.set_thumbnail(url=self.target_user.display_avatar.url)
        await itx.response.send_message(embed=embed, ephemeral=True)

class PointSetModal(discord.ui.Modal, title="ポイントを直接設定"):
    amount_input = discord.ui.TextInput(
        label="設定するポイント数",
        placeholder="例: 500",
        required=True
    )

    def __init__(self, target_user):
        super().__init__()
        self.target_user = target_user

    async def on_submit(self, itx: discord.Interaction):
        try:
            amount = int(self.amount_input.value)
        except ValueError:
            await itx.response.send_message("❌ 数字を入力してください", ephemeral=True)
            return
        
        new_total = set_points(self.target_user.id, amount)
        
        embed = discord.Embed(
            title="✅ ポイント設定完了",
            description=f"{self.target_user.mention} を {new_total}P に設定しました",
            color=0x3498DB,
            timestamp=datetime.now(JST)
        )
        embed.set_thumbnail(url=self.target_user.display_avatar.url)
        await itx.response.send_message(embed=embed, ephemeral=True)

# ✅ ユーザー選択をModalに直接変更（古いバージョン対応）
class PointAdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="➕ ポイントを付与", style=discord.ButtonStyle.success, custom_id="point_admin:add", row=0)
    async def add_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.send_message(
            "➕ 対象のユーザーをメンションして数字を入力してください。\n"
            "例：`@ユーザー 100` または `@ユーザー -50`",
            ephemeral=True
        )

    @discord.ui.button(label="✏️ ポイントを設定", style=discord.ButtonStyle.primary, custom_id="point_admin:set", row=0)
    async def set_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.send_message(
            "✏️ 対象のユーザーをメンションして設定する数字を入力してください。\n"
            "例：`@ユーザー 500`",
            ephemeral=True
        )

    @discord.ui.button(label="💳 ポイント確認", style=discord.ButtonStyle.secondary, custom_id="point_admin:check", row=1)
    async def check_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.send_message(
            "💳 確認したいユーザーをメンションしてください。\n"
            "例：`@ユーザー`",
            ephemeral=True
        )

    @discord.ui.button(label="🗑️ 0にリセット", style=discord.ButtonStyle.danger, custom_id="point_admin:reset", row=1)
    async def reset_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.send_message(
            "🗑️ 0にするユーザーをメンションしてください。\n"
            "例：`@ユーザー`",
            ephemeral=True
        )

async def setup(tree: app_commands.CommandTree):
    @tree.command(name="ポイント付与", description="ユーザーにポイントを付与（オーナー専用）")
    @app_commands.check(is_owner)
    async def cmd_add(itx: discord.Interaction, user: discord.User, amount: int):
        new_total = add_points(user.id, amount)
        embed = discord.Embed(
            title="✅ ポイント付与完了",
            description=f"{user.mention} に {amount:+d}P しました\n現在: **{new_total}P**",
            color=0x2ECC71,
            timestamp=datetime.now(JST)
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await itx.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="ポイント設定", description="ユーザーのポイントを直接設定（オーナー専用）")
    @app_commands.check(is_owner)
    async def cmd_set(itx: discord.Interaction, user: discord.User, amount: int):
        new_total = set_points(user.id, amount)
        embed = discord.Embed(
            title="✅ ポイント設定完了",
            description=f"{user.mention} を {new_total}P に設定しました",
            color=0x3498DB,
            timestamp=datetime.now(JST)
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await itx.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="ポイント確認", description="ユーザーのポイントを確認（オーナー専用）")
    @app_commands.check(is_owner)
    async def cmd_check(itx: discord.Interaction, user: discord.User):
        pts = get_points(user.id)
        embed = discord.Embed(
            title="💳 ポイント確認",
            description=f"{user.mention} のポイント：**{pts}P**",
            color=0xF1C40F,
            timestamp=datetime.now(JST)
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await itx.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="ポイントリセット", description="ユーザーのポイントを0にリセット（オーナー専用）")
    @app_commands.check(is_owner)
    async def cmd_reset(itx: discord.Interaction, user: discord.User):
        set_points(user.id, 0)
        embed = discord.Embed(
            title="🗑️ ポイントリセット完了",
            description=f"{user.mention} のポイントを0にしました",
            color=0xE74C3C,
            timestamp=datetime.now(JST)
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await itx.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="ポイント付与パネル設置", description="ポイント管理パネル設置（オーナー専用）")
    @app_commands.check(is_owner)
    async def cmd_panel(itx: discord.Interaction):
        embed = discord.Embed(
            title="💳 ポイント管理パネル",
            description="""➕ **/ポイント付与 @ユーザー 数値** → ポイント増減
✏️ **/ポイント設定 @ユーザー 数値** → 値を直接設定
💳 **/ポイント確認 @ユーザー** → 現在のポイント表示
🗑️ **/ポイントリセット @ユーザー** → 0にリセット
🔒 オーナー以外は操作できません""",
            color=0xF1C40F,
            timestamp=datetime.now(JST)
        )
        await itx.response.send_message(embed=embed, view=PointAdminView())
        await itx.followup.send("✅ ポイント付与パネル設置完了", ephemeral=True)
