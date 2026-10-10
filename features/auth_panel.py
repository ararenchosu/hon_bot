import discord
from discord import app_commands
from core.common import is_owner

class AuthPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ 鯖メン認証", style=discord.ButtonStyle.primary, custom_id="auth:get")
    async def get_role(self, itx, btn):
        role = discord.utils.get(itx.guild.roles, name="鯖メン")
        if not role:
            await itx.response.send_message("❌ 「鯖メン」ロールが存在しません。先にロールを作成してください。", ephemeral=True)
            return
        if role in itx.user.roles:
            await itx.response.send_message("✅ 既に認証済みです！", ephemeral=True)
            return
        await itx.user.add_roles(role)
        await itx.response.send_message(f"✅ 「鯖メン」ロールを付与しました！", ephemeral=True)

    @discord.ui.button(label="✏️ パネル編集", style=discord.ButtonStyle.secondary, custom_id="auth:edit")
    async def edit_panel(self, itx, btn):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return
        class AuthEditModal(discord.ui.Modal, title="認証パネル編集"):
            title_in = discord.ui.TextInput(label="タイトル", default="🔐 サーバー認証")
            desc_in = discord.ui.TextInput(
                label="説明", style=discord.TextStyle.long,
                default="下のボタンを押して「鯖メン」ロールを取得してください。"
            )
            async def on_submit(self, inter):
                embed = discord.Embed(title=str(self.title_in), description=str(self.desc_in), color=0x2ecc71)
                await inter.response.edit_message(embed=embed)
                await inter.followup.send("✅ 更新しました", ephemeral=True)
        await itx.response.send_modal(AuthEditModal())

async def setup(tree):
    @tree.command(name="認証パネル設置", description="鯖認証パネル設置（オーナー専用）")
    async def cmd_auth_panel(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用コマンドです", ephemeral=True)
            return
        embed = discord.Embed(
            title="🔐 サーバー認証",
            description="下のボタンを押して「鯖メン」ロールを取得してください。",
            color=0x2ecc71
        )
        await itx.response.send_message(embed=embed, view=AuthPanelView())
