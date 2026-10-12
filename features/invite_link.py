import discord
from discord import app_commands
from core.common import is_owner
import qrcode
import io


class InviteDurationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="♾️ 永久", style=discord.ButtonStyle.success)
    async def forever(self, itx: discord.Interaction, btn: discord.ui.Button):
        await self._generate(itx, max_age=0)

    @discord.ui.button(label="⏱️ 24時間", style=discord.ButtonStyle.primary)
    async def day1(self, itx: discord.Interaction, btn: discord.ui.Button):
        await self._generate(itx, max_age=86400)

    @discord.ui.button(label="📅 7日", style=discord.ButtonStyle.primary)
    async def day7(self, itx: discord.Interaction, btn: discord.ui.Button):
        await self._generate(itx, max_age=604800)

    async def _generate(self, itx: discord.Interaction, max_age: int):
        # 招待リンク作成
        invite = await itx.channel.create_invite(
            max_age=max_age,
            max_uses=0,
            unique=True
        )

        # 期限表示
        if max_age == 0:
            expiry_text = "永久"
        elif max_age == 86400:
            expiry_text = "24時間"
        else:
            expiry_text = "7日"

        # ✅ QRコード生成
        qr_img = qrcode.make(invite.url)
        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        buffer.seek(0)
        qr_file = discord.File(fp=buffer, filename="invite_qr.png")

        # DMに送信
        dm_success = False
        try:
            await itx.user.send(
                f"✅ サーバー招待リンク\n"
                f"🔗 {invite.url}\n"
                f"⏳ 有効期限：{expiry_text}",
                file=qr_file
            )
            dm_success = True
        except Exception as e:
            print(f"DM送信エラー: {e}")
            pass

        # 結果表示
        if dm_success:
            message = f"✅ 招待リンク＋QRコードをDMに送信しました！\n🔗 {invite.url}"
        else:
            message = f"⚠️ DMに送信できませんでした。こちらがリンクです👇\n🔗 {invite.url}"

        await itx.response.edit_message(content=message, view=None)


class InvitePanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔗 招待リンクを生成",
        style=discord.ButtonStyle.primary,
        custom_id="invite:panel"
    )
    async def create_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return

        await itx.response.send_message(
            "⏳ リンクの有効期限を選択してください",
            view=InviteDurationView(),
            ephemeral=True
        )


async def setup(tree: app_commands.CommandTree):
    bot = tree.client
    bot.add_view(InvitePanelView())
    bot.add_view(InviteDurationView())

    @tree.command(
        name="招待リンクパネル",
        description="招待リンク生成パネルを表示（オーナー専用）"
    )
    @app_commands.check(is_owner)
    async def invite_panel_cmd(itx: discord.Interaction):
        embed = discord.Embed(
            title="🔗 招待リンク生成",
            description="下のボタンを押して招待リンクを作成できます\n"
                        "✅ リンク＋QRコードがDMに送信されます\n"
                        "※ サーバー側にログは残りません",
            color=0x3498DB
        )
        await itx.response.send_message(embed=embed, view=InvitePanelView())
        await itx.followup.send("✅ パネルを表示しました", ephemeral=True)
