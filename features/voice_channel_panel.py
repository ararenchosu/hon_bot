import discord
from discord import app_commands
import asyncio
import random
from datetime import datetime, timedelta, timezone
from core.common import is_owner

JST = timezone(timedelta(hours=9))

# ✅ 設定
CATEGORY_ID = 1558099663922405376          # 一時通話カテゴリ
LOG_CREATE_DELETE_CHANNEL = 1558734928366141460  # 作成・削除ログ
LOG_JOIN_LEAVE_CHANNEL = 1558735006103371826     # 入室・退出ログ
TIMEOUT_NO_JOIN = 120  # 作成後誰も入らないと削除：2分
TIMEOUT_EMPTY = 5      # 0人になってから削除：5秒

# チャンネル管理データ
active_channels = {}


def format_time(seconds: int) -> str:
    """秒数を「X分X秒」形式に整形"""
    if seconds < 60:
        return f"{seconds}秒"
    m = seconds // 60
    s = seconds % 60
    if s == 0:
        return f"{m}分"
    return f"{m}分{s}秒"


def jst_str(timestamp: float) -> str:
    """タイムスタンプをJST時刻文字列「HH:MM:SS」に変換"""
    return datetime.fromtimestamp(timestamp, JST).strftime("%H:%M:%S")


async def send_create_log(client: discord.Client, channel_name: str, creator: discord.User):
    log_ch = client.get_channel(LOG_CREATE_DELETE_CHANNEL)
    if not log_ch:
        print(f"⚠️ 作成ログチャンネルが見つかりません: {LOG_CREATE_DELETE_CHANNEL}")
        return
    embed = discord.Embed(
        title="📞 通話チャンネル作成",
        color=0x2ECC71,
        timestamp=datetime.now(JST)
    )
    embed.add_field(name="🔊 チャンネル名", value=channel_name, inline=False)
    embed.add_field(name="👤 作成者", value=creator.mention, inline=False)
    embed.set_thumbnail(url=creator.display_avatar.url)
    await log_ch.send(embed=embed)


async def send_delete_summary_log(client: discord.Client, channel_name: str, reason: str, member_records: list):
    log_ch = client.get_channel(LOG_CREATE_DELETE_CHANNEL)
    if not log_ch:
        print(f"⚠️ 削除ログチャンネルが見つかりません: {LOG_CREATE_DELETE_CHANNEL}")
        return

    embed = discord.Embed(
        title="🗑️ 通話チャンネル削除",
        color=0xE74C3C,
        timestamp=datetime.now(JST)
    )
    embed.add_field(name="🔊 チャンネル名", value=channel_name, inline=False)
    embed.add_field(name="📝 理由", value=reason, inline=False)

    if member_records:
        member_lines = []
        first_join = None
        last_leave = None
        max_stay = 0
        for rec in member_records:
            join_str = jst_str(rec["join_ts"])
            leave_str = jst_str(rec["leave_ts"])
            line = f"{rec['mention']} ｜ 入室{join_str} ／ 退出{leave_str} ／ 在籍{format_time(rec['stay_sec'])}"
            member_lines.append(line)
            if first_join is None or rec["join_ts"] < first_join:
                first_join = rec["join_ts"]
            if last_leave is None or rec["leave_ts"] > last_leave:
                last_leave = rec["leave_ts"]
            if rec["stay_sec"] > max_stay:
                max_stay = rec["stay_sec"]

        embed.add_field(
            name=f"👥 参加者一覧（{len(member_records)}人）",
            value="\n".join(member_lines),
            inline=False
        )
        embed.add_field(
            name="📊 まとめ",
            value=(
                f"延べ参加人数：{len(member_records)}人\n"
                f"最長在籍：{format_time(max_stay)}\n"
                f"通話期間：{jst_str(first_join)} ～ {jst_str(last_leave)}"
            ),
            inline=False
        )
    else:
        embed.add_field(name="👥 参加者", value="なし", inline=False)

    await log_ch.send(embed=embed)


async def send_join_log(client: discord.Client, channel_name: str, user: discord.User, join_time: float):
    log_ch = client.get_channel(LOG_JOIN_LEAVE_CHANNEL)
    if not log_ch:
        print(f"⚠️ 入室ログチャンネルが見つかりません: {LOG_JOIN_LEAVE_CHANNEL}")
        return
    embed = discord.Embed(
        title="📥 入室",
        color=0x3498DB,
        timestamp=datetime.now(JST)
    )
    embed.add_field(name="🔊 チャンネル", value=channel_name, inline=False)
    embed.add_field(name="👤 ユーザー", value=user.mention, inline=False)
    embed.add_field(name="🕐 時間", value=jst_str(join_time), inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    await log_ch.send(embed=embed)


async def send_leave_log(client: discord.Client, channel_name: str, user: discord.User, leave_time: float, stay_sec: int):
    log_ch = client.get_channel(LOG_JOIN_LEAVE_CHANNEL)
    if not log_ch:
        print(f"⚠️ 退出ログチャンネルが見つかりません: {LOG_JOIN_LEAVE_CHANNEL}")
        return
    embed = discord.Embed(
        title="📤 退出",
        color=0xF39C12,
        timestamp=datetime.now(JST)
    )
    embed.add_field(name="🔊 チャンネル", value=channel_name, inline=False)
    embed.add_field(name="👤 ユーザー", value=user.mention, inline=False)
    embed.add_field(name="🕐 時間", value=jst_str(leave_time), inline=False)
    embed.add_field(name="⏱️ 在籍時間", value=format_time(stay_sec), inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    await log_ch.send(embed=embed)


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

        name = str(self.room_name)
        for ch in category.channels:
            if ch.name == name and isinstance(ch, discord.VoiceChannel):
                await itx.response.send_message(
                    f"❌ 「{name}」は既に存在します。別の名前にしてください。",
                    ephemeral=True
                )
                return

        overwrites = {
            itx.guild.default_role: discord.PermissionOverwrite(
                view_channel=True, connect=True
            ),
            itx.user: discord.PermissionOverwrite(
                manage_channels=True, move_members=True,
                mute_members=True, deafen_members=True,
                view_channel=True, connect=True
            )
        }

        voice_channel = await category.create_voice_channel(
            name=name, overwrites=overwrites,
            reason=f"一時通話ルーム作成: {itx.user}"
        )

        await send_create_log(itx.client, voice_channel.name, itx.user)

        await itx.response.send_message(
            f"✅ 通話チャンネルを作成しました！\n🔊 {voice_channel.mention}\n⚠️ 2分以内に入室が確認されない場合は自動削除されます。",
            ephemeral=True
        )

        active_channels[voice_channel.id] = {
            "task": None,
            "channel_name": voice_channel.name,
            "member_records": {}
        }

        task = asyncio.create_task(watch_channel(voice_channel))
        active_channels[voice_channel.id]["task"] = task


async def watch_channel(channel: discord.VoiceChannel):
    client = channel.guild._state._get_client()
    channel_id = channel.id
    channel_name = channel.name
    last_members = set()

    try:
        # ===== フェーズ1：作成後2分間、誰も入らなければ削除 =====
        for _ in range(TIMEOUT_NO_JOIN):
            if channel_id not in active_channels:
                return
            current_members = set(channel.members)
            for member in current_members - last_members:
                if member.bot:
                    continue
                now_ts = datetime.now(JST).timestamp()
                active_channels[channel_id]["member_records"][member.id] = {
                    "mention": member.mention,
                    "join_ts": now_ts,
                    "leave_ts": None,
                    "stay_sec": None
                }
                await send_join_log(client, channel_name, member, now_ts)
            last_members = current_members
            if len(current_members) > 0:
                break
            await asyncio.sleep(1)
        else:
            if channel.guild.get_channel(channel_id):
                records = list(active_channels[channel_id]["member_records"].values())
                await send_delete_summary_log(client, channel_name, "2分以内に入室がないため", records)
                await channel.delete(reason="2分以内に入室がないため")
            return

        # ===== フェーズ2：常時監視 =====
        while True:
            if channel_id not in active_channels:
                return
            current_members = set(channel.members)

            # 入室
            for member in current_members - last_members:
                if member.bot:
                    continue
                now_ts = datetime.now(JST).timestamp()
                active_channels[channel_id]["member_records"][member.id] = {
                    "mention": member.mention,
                    "join_ts": now_ts,
                    "leave_ts": None,
                    "stay_sec": None
                }
                await send_join_log(client, channel_name, member, now_ts)

            # 退出
            for member in last_members - current_members:
                if member.bot:
                    continue
                rec = active_channels[channel_id]["member_records"].get(member.id)
                if rec and rec["leave_ts"] is None:
                    leave_ts = datetime.now(JST).timestamp()
                    stay_sec = int(leave_ts - rec["join_ts"])
                    rec["leave_ts"] = leave_ts
                    rec["stay_sec"] = stay_sec
                    await send_leave_log(client, channel_name, member, leave_ts, stay_sec)

            last_members = current_members

            # 0人になったら5秒待って削除
            if len(current_members) == 0:
                await asyncio.sleep(TIMEOUT_EMPTY)
                ch = channel.guild.get_channel(channel_id)
                if ch and len(ch.members) == 0:
                    records = list(active_channels[channel_id]["member_records"].values())
                    await send_delete_summary_log(client, channel_name, "誰もいなくなったため自動削除", records)
                    await ch.delete(reason="誰もいないため自動削除")
                    return

            await asyncio.sleep(1)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"⚠️ チャンネル監視エラー: {e}")
    finally:
        active_channels.pop(channel_id, None)


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
    await channel.send(embed=embed, view=VoiceCreatePanelView())


async def setup(tree: app_commands.CommandTree):
    @tree.command(name="通話パネル設置", description="一時通話チャンネル作成パネルを設置（オーナー専用）")
    async def setup_voice_panel(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用コマンドです", ephemeral=True)
            return
        await setup_panel(itx.channel)
        await itx.response.send_message("✅ パネルを設置しました", ephemeral=True)
