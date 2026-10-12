import discord
from discord import app_commands
from core.common import is_owner
import qrcode
import io


class InviteDurationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="♾️ 永久",
        style=discord.ButtonStyle.success,
        custom_id="invite:duration_forever"
    )
    async def forever(self, itx: discord.Interaction, btn: discord.ui.Button):
        await self._generate(itx, max_age=0)

    @discord.ui.button(
        label="⏱️ 24時間",
        style=discord.ButtonStyle.primary,
        custom_id="invite:duration_24h"
    )
    async def day1(self, itx: discord.Interaction, btn: discord.ui.Button):
        await self._generate(itx, max_age=86400)

    @discord.ui.button(
        label="📅 7日",
        style=discord.ButtonStyle.primary,
        custom_id="invite:duration_7d"
    )
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

        # QRコード生成
        qr_img = qrcode.make(invite.url)
        qr_img = qr_img.resize((200, 200))  # サイズ調整
        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        buffer.seek(0)
        qr_file = discord.File(fp=buffer, filename="qrcode.png")

        # ✅ 埋め込み：左にリンク、右にQRコード
        embed = discord.Embed(
            title="🔗 サーバー招待リンク",
            description="👇 リンクをタップまたは長押しでコピー！",
            color=0x2ECC71
        )
        embed.add_field(
            name="📋 招待リンク",
            value=f"```\n{invite.url}\n```\n⏳ 有効期限：{expiry_text}",
            inline=True
        )
        # 空フィールドでスペースを作ってからQRコードを配置
        embed.add_field(name="　", value="　", inline=True)
        embed.set_thumbnail(url="attachment://qrcode.png")  # ✅ 右横にQRコード

        # ボタン
        dm_view = discord.ui.View()
        dm_view.add_item(discord.ui.Button(
            label="🔗 ブラウザで開く",
            style=discord.ButtonStyle.link,
            url=invite.url
        ))

        # DMに送信
        dm_success = False
        try:
            await itx.user.send(embed=embed, file=qr_file, view=dm_view)
            dm_success = True
        except Exception as e:
            print(f"DM送信エラー: {e}")

        # 結果表示
        if dm_success:
            message = (
                "✅ 招待リンクをDMに送信しました！\n"
                "リンクをタップ → コピー または QRコードを読み取ってください"
            )
        else:
            message = f"⚠️ DMに送信できませんでした。こちらをコピーしてください👇\n```\n{invite.url}\n```"

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
                        "✅ リンク＋QRコードがDMに届きます\n"
                        "※ サーバー側にログは残りません",
            color=0x3498DB
        )
        await itx.response.send_message(embed=embed, view=InvitePanelView())
        await itx.followup.send("✅ パネルを表示しました", ephemeral=True)
