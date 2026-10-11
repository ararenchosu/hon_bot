import discord
from discord import app_commands
from core.common import is_owner
from features.lottery_panel import point_data  # ✅ 既存のポイントデータを共有


class LoginBonusPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎁 ログインボーナス受取", style=discord.ButtonStyle.primary, custom_id="loginbonus:receive")
    async def receive_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not point_data.can_draw_today(itx.user.id):
            await itx.response.send_message(
                "✅ 今日は既に受け取り済みです。また明日お待ちください✨",
                ephemeral=True
            )
            return
        
        # ✅ 100ポイント付与
        point_data.mark_drew_today(itx.user.id)
        new_points = point_data.add_points(itx.user.id, 100)
        
        await itx.response.send_message(
            f"🎉 ログインボーナス受け取り完了！\n"
            f"➕ 100ポイント 獲得✨\n"
            f"💳 現在のポイント：{new_points}ポイント",
            ephemeral=True
        )

    @discord.ui.button(label="✏️ パネル編集", style=discord.ButtonStyle.secondary, custom_id="loginbonus:edit")
    async def edit_bonus_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return
        class BonusEditModal(discord.ui.Modal, title="ログインボーナス編集"):
            title_in = discord.ui.TextInput(
                label="タイトル",
                default="🎁 毎日ログインボーナス",
                required=True
            )
            desc_in = discord.ui.TextInput(
                label="説明文",
                style=discord.TextStyle.long,
                default="下のボタンを押すと1日1回100ポイントがもらえます✨",
                required=True
            )
            async def on_submit(self, m_itx: discord.Interaction):
                embed = discord.Embed(
                    title=str(self.title_in),
                    description=str(self.desc_in),
                    color=0x00FF7F
                )
                await m_itx.response.edit_message(embed=embed, view=LoginBonusPanelView())
                await m_itx.followup.send("✅ パネルを更新しました", ephemeral=True)
        await itx.response.send_modal(BonusEditModal())


async def setup(tree):
    @tree.command(name="ログインボーナスパネル設置", description="ログインボーナスパネルを設置（オーナー専用）")
    async def cmd_login_bonus_panel(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return
        embed = discord.Embed(
            title="🎁 毎日ログインボーナス",
            description="下のボタンを押すと1日1回 **100ポイント** がもらえます✨\n"
                        "※くじ引きと受け取りは共通です",
            color=0x00FF7F
        )
        await itx.response.send_message(embed=embed, view=LoginBonusPanelView())
