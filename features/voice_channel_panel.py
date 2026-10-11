import discord
from discord import app_commands
import asyncio
import random

# ✅ 設定
CATEGORY_ID = 1558099663922405376  # 一時ルーム用カテゴリID
TIMEOUT_NO_JOIN = 120  # 作成後誰も入らない場合のタイムアウト：2分（秒）
TIMEOUT_EMPTY = 5      # 誰もいなくなってから削除まで：5秒

# 管理中のチャンネルとタスクを保持
active_channels = {}  # {channel_id: task}

class RoomNameModal(discord.ui.Modal, title="通話ルーム名を入力"):
    room_name = discord.ui.TextInput(
        label="チャンネル名",
        placeholder="例：荒野行動対戦 / メンバーと雑談",
        required=True,
        max_length=30
    )

    async def on_submit(self, itx: discord.Interaction):
        category = itx.guild.get_channel(CATEGORY_ID)
        if not category or not isinstance(category, discord.CategoryChannel):
            await itx.response.send_message("❌ カテゴリが見つかりません", ephemeral=True)
            return

        # チャンネル名の重複チェック
        name = str(self.room_name)
        for ch in category.channels:
            if ch.name == name and isinstance(ch, discord.VoiceChannel):
                await itx.response.send_message(
                    f"❌ 「{name}」は既に存在します。別の名前にしてください。",
                    ephemeral=True
                )
                return

        # チャンネル作成
        overwrites = {
            itx.guild.default_role: discord.PermissionOverwrite(
                view_channel=True,
                connect=True
            ),
            itx.user: discord.PermissionOverwrite(
                manage_channels=True,
                move_members=True,
                mute_members=True,
                deafen_members=True,
                view_channel=True,
                connect=True
            )
        }

        voice_channel = await category.create_voice_channel(
            name=name,
            overwrites=overwrites,
            reason=f"一時通話ルーム作成: {itx.user}"
        )

        await itx.response.send_message(
            f"✅ 通話チャンネルを作成しました！\n🔊 {voice_channel.mention}\n⚠️ 2分以内に入室が確認されない場合は自動削除されます。",
            ephemeral=True
        )

        # 監視タスク開始
        task = asyncio.create_task(watch_channel(voice_channel))
        active_channels[voice_channel.id] = task


async def watch_channel(channel: discord.VoiceChannel):
    """チャンネルの状態を監視し、条件を満たしたら削除"""
    try:
        # 【フェーズ1】作成後2分間：誰も入らなければ削除
        for _ in range(TIMEOUT_NO_JOIN):
            if len(channel.members) > 0:
                break  # 誰かが入った → 次のフェーズへ
            await asyncio.sleep(1)
        else:
            # 2分間誰も入らなかった
            if channel.guild.get_channel(channel.id):
                await channel.delete(reason="2分以内に入室がないため")
            return

        # 【フェーズ2】通常監視：0人になったら5秒後に削除
        while True:
            if len(channel.members) == 0:
                await asyncio.sleep(TIMEOUT_EMPTY)
                # 5秒後に再確認
                ch = channel.guild.get_channel(channel.id)
                if ch and len(ch.members) == 0:
                    await ch.delete(reason="誰もいないため自動削除")
                    return
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"⚠️ チャンネル監視エラー: {e}")
    finally:
        active_channels.pop(channel.id, None)


class VoiceCreatePanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔊 通話ルームを作成",
        style=discord.ButtonStyle.primary,
        custom_id="voice:create"
    )
    async def create_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        await itx.response.send_modal(RoomNameModal())

    @discord.ui.button(
        label="✏️ パネル編集",
        style=discord.ButtonStyle.secondary,
        custom_id="voice:edit"
    )
    async def edit_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        from core.common import is_owner
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return

        class PanelEditModal(discord.ui.Modal, title="パネル編集"):
            title_in = discord.ui.TextInput(
                label="パネルタイトル",
                default="通話チャンネル作成",
                required=True
            )
            desc_in = discord.ui.TextInput(
                label="説明文",
                default="⬇️のボタンを押すと通話チャンネルが作成できます。作成者の方は2分以内の入出をお願いします。入出が確認されなかった場合チャンネル自動消去されます。通話終了後5秒でチャンネル消去になります。",
                style=discord.TextStyle.long,
                required=True
            )

            async def on_submit(self, m_itx: discord.Interaction):
                colors = [
                    discord.Color.blue(), discord.Color.green(),
                    discord.Color.gold(), discord.Color.orange(),
                    discord.Color.purple(), discord.Color.pink(),
                    discord.Color.teal(), discord.Color.magenta()
                ]
                embed = discord.Embed(
                    title=str(self.title_in),
                    description=str(self.desc_in),
                    color=random.choice(colors)
                )
                await m_itx.response.edit_message(embed=embed)
                await m_itx.followup.send("✅ パネルを更新しました", ephemeral=True)

        await itx.response.send_modal(PanelEditModal())


async def setup_panel(channel):
    """パネルを送信するコマンド用関数"""
    colors = [
        discord.Color.blue(), discord.Color.green(),
        discord.Color.gold(), discord.Color.orange(),
        discord.Color.purple(), discord.Color.pink(),
        discord.Color.teal(), discord.Color.magenta()
    ]
    embed = discord.Embed(
        title="通話チャンネル作成",
        description="⬇️のボタンを押すと通話チャンネルが作成できます。作成者の方は2分以内の入出をお願いします。入出が確認されなかった場合チャンネル自動消去されます。通話終了後5秒でチャンネル消去になります。",
        color=random.choice(colors)
    )
    view = VoiceCreatePanelView()
    await channel.send(embed=embed, view=view)


async def setup(tree: app_commands.CommandTree):
    # 起動時に監視タスクを回復する場合の処理を登録
    pass
