import discord
from discord import app_commands
from core.common import is_owner
import qrcode
import io

# ✅ 許可するロール名
ALLOWED_MEMBER_ROLE = "鯖メン"

# ========== 共通：権限チェック ==========
def has_member_role(user: discord.Member) -> bool:
    """@鯖メンロールを持っているか確認"""
    return any(role.name == ALLOWED_MEMBER_ROLE for role in user.roles)

class InviteDurationView(discord.ui.View):
    def __init__(self, is_owner_user: bool = False):
        super().__init__(timeout=None)
        self.is_owner_user = is_owner_user

        # ✅ オーナー以外は7日・永久ボタンを削除
        if not is_owner_user:
            # 7日ボタンを削除
            for item in self.children:
                if hasattr(item, 'custom_id') and item.custom_id in ("invite:duration_7d", "invite:duration_forever"):
                    self.remove_item(item)

    @discord.ui.button(
        label="♾️ 永久",
        style=discord.ButtonStyle.success,
        custom_id="invite:duration_forever"
    )
    async def forever(self, itx: discord.Interaction, btn: discord.ui.Button):
        # ✅ オーナーだけ許可
        if not is_owner(itx):
            await itx.response.send_message("❌ この期限はオーナー専用です", ephemeral=True)
            return
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
        # ✅ オーナーだけ許可
        if not is_owner(itx):
            await itx.response.send_message("❌ この期限はオーナー専用です", ephemeral=True)
            return
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
        qr_img = qr_img.resize((200, 200))
        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        buffer.seek(0)
        qr_file = discord.File(fp=buffer, filename="qrcode.png")
        # 埋め込み
        embed = discord.Embed(
            title="🔗 サーバー招待リンク",
            description="👇 リンクを押すとブラウザが開きます",
            color=0x2ECC71
        )
        embed.add_field(
            name="📋 招待リンク",
            value=f"[👉 ここを押してリンクを開く]({invite.url})\n```\n{invite.url}\n```\n⏳ 有効期限：{expiry_text}",
            inline=True
        )
        embed.add_field(name="　", value="　", inline=True)
        embed.set_thumbnail(url="attachment://qrcode.png")
        # ボタン
        dm_view = discord.ui.View()
        dm_view.add_item(discord.ui.Button(
            label="🔗 ブラウザで開く",
            style=discord.ButtonStyle.link,
            url=invite.url
        ))
        # DM送信
        dm_success = False
        try:
            await itx.user.send(embed=embed, file=qr_file, view=dm_view)
            dm_success = True
        except Exception as e:
            print(f"DM送信エラー: {e}")
        # 結果
        if dm_success:
            message = (
                "✅ 招待リンクをDMに送信しました！\n"
                "リンクを押す → 開く / テキスト部分をコピー どちらも可能です"
            )
        else:
            message = f"⚠️ DMに送信できませんでした👇\n[👉 ここを押して開く]({invite.url})\n```\n{invite.url}\n```"
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
        # ✅ 権限チェック：オーナー または @鯖メン のみ許可
        owner_check = is_owner(itx)
        member_check = has_member_role(itx.user)

        if not owner_check and not member_check:
            await itx.response.send_message(
                "❌ この機能は「@鯖メン」またはオーナーのみ利用できます",
                ephemeral=True
            )
            return

        # ✅ 権限に応じて表示するボタンを分岐
        is_owner_user = owner_check
        await itx.response.send_message(
            "⏳ リンクの有効期限を選択してください",
            view=InviteDurationView(is_owner_user=is_owner_user),
            ephemeral=True
        )

async def setup(tree: app_commands.CommandTree):
    bot = tree.client
    bot.add_view(InvitePanelView())
    # InviteDurationView は動的に生成するためここでは登録しない

    @tree.command(
        name="招待リンクパネル",
        description="招待リンク生成パネルを表示（鯖メン以上）"
    )
    async def invite_panel_cmd(itx: discord.Interaction):
        # ✅ コマンド実行時も権限チェック
        owner_check = is_owner(itx)
        member_check = has_member_role(itx.user)

        if not owner_check and not member_check:
            await itx.response.send_message(
                "❌ この機能は「@鯖メン」またはオーナーのみ利用できます",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🔗 招待リンク生成",
            description="下のボタンを押して招待リンクを作成できます\n"
                        "✅ 押して開く・テキストからコピー 両方可能\n"
                        "※ サーバー側にログは残りません",
            color=0x3498DB
        )
        if owner_check:
            embed.add_field(
                name="📝 ユーザー種別",
                value="👑 オーナー — 24時間 / 7日 / 永久 選択可",
                inline=False
            )
        else:
            embed.add_field(
                name="📝 ユーザー種別",
                value="👤 鯖メン — 24時間限定で発行可",
                inline=False
            )

        await itx.response.send_message(embed=embed, view=InvitePanelView())
        await itx.followup.send("✅ パネルを表示しました", ephemeral=True)
