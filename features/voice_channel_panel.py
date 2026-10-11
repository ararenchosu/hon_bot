import discord
from discord import app_commands
import asyncio
import random
from datetime import datetime, timedelta, timezone
from core.common import is_owner
import gtts
import io

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
    if seconds < 60:
        return f"{seconds}秒"
    m = seconds // 60
    s = seconds % 60
    if s == 0:
        return f"{m}分"
    return f"{m}分{s}秒"


def jst_str(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, JST).strftime("%H:%M:%S")


def make_tts_audio(text: str) -> io.BytesIO:
    tts = gtts.gTTS(text=text, lang="ja")
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp


async def speak_in_channel(voice_channel, text: str):
    """指定チャンネルで読み上げ - 最終確実版"""
    if not voice_channel:
        print("⚠️ チャンネルがNoneです")
        return
    try:
        client = voice_channel.guild._state._get_client()
        print(f"🔊 読み上げ開始: {text} / チャンネル: {voice_channel.name}")

        # 既に接続されているか確認
        vc = None
        for conn in client.voice_clients:
            if conn.guild.id == voice_channel.guild.id:
                vc = conn
                break

        # 接続されていなければ入る
        if not vc or not vc.is_connected():
            print(f"🔊 チャンネルに接続します...")
            vc = await voice_channel.connect()
            print(f"✅ 接続完了: {voice_channel.name}")
        elif vc.channel.id != voice_channel.id:
            print(f"🔊 チャンネルを移動: {vc.channel.name} → {voice_channel.name}")
            await vc.move_to(voice_channel)

        # 再生中なら待つ
        while vc.is_playing():
            await asyncio.sleep(0.3)

        # 音声生成・再生
        audio_fp = await asyncio.to_thread(make_tts_audio, text)
        source = discord.FFmpegPCMAudio(audio_fp, pipe=True)
        vc.play(source)
        print(f"🔊 再生中: {text}")

        while vc.is_playing():
            await asyncio.sleep(0.3)

        # 他にメンバーがいなければ切断
        if len(voice_channel.members) == 1:
            await vc.disconnect()
            print(f"🔌 誰もいないので切断しました")

    except Exception as e:
        print(f"⚠️ 音声読み上げエラー: {type(e).__name__}: {e}")


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
        # ✅ 先に応答を返してタイムアウト回避
        await itx.response.defer(ephemeral=True)

        category = itx.guild.get_channel(CATEGORY_ID)
        if not category or not isinstance(category, discord.CategoryChannel):
            await itx.followup.send("❌ カテゴリが見つかりません", ephemeral=True)
            return

        name = str(self.room_name)
        for ch in category.channels:
            if ch.name == name and isinstance(ch, discord.VoiceChannel):
                await itx.followup.send(
                    f"❌ 「{name}」は既に存在します。別の名前にしてください。",
                    ephemeral=True
                )
                return

        overwrites = {
            itx.guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=True),
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
        await itx.followup.send(
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
    print(f"👀 監視開始: {channel_name}")

    try:
        # ===== フェーズ1：作成後2分間、誰も入らなければ削除 =====
        for _ in range(TIMEOUT_NO_JOIN):
            if channel_id not in active_channels:
                return
            ch = client.get_channel(channel_id)
            if not ch:
                print(f"🗑️ チャンネルが既に削除されています: {channel_name}")
                return
            current_members = set(ch.members)

            for member in current_members - last_members:
                if member.bot:
                    continue
                print(f"📥 入室検知: {member.display_name}")
                now_ts = datetime.now(JST).timestamp()
                active_channels[channel_id]["member_records"][member.id] = {
                    "mention": member.mention,
                    "join_ts": now_ts,
                    "leave_ts": None,
                    "stay_sec": None
                }
                await send_join_log(client, channel_name, member, now_ts)
                asyncio.create_task(speak_in_channel(ch, f"{member.display_name}さんが入室しました"))

            last_members = current_members
            if len(current_members) > 0:
                break
            await asyncio.sleep(1)
        else:
            # 2分間誰も入室なし
            ch = client.get_channel(channel_id)
            if ch:
                print(f"⏰ 2分経過・誰も入室なし → 削除: {channel_name}")
                records = list(active_channels[channel_id]["member_records"].values())
                await send_delete_summary_log(client, channel_name, "2分以内に入室がないため", records)
                for vc in client.voice_clients:
                    if vc.channel and vc.channel.id == channel_id:
                        await vc.disconnect()
                await ch.delete(reason="2分以内に入室がないため")
            return

        # ===== フェーズ2：常時監視 =====
        while True:
            if channel_id not in active_channels:
                return
            ch = client.get_channel(channel_id)
            if not ch:
                return
            current_members = set(ch.members)

            # 入室
            for member in current_members - last_members:
                if member.bot:
                    continue
                print(f"📥 入室: {member.display_name}")
                now_ts = datetime.now(JST).timestamp()
                active_channels[channel_id]["member_records"][member.id] = {
                    "mention": member.mention,
                    "join_ts": now_ts,
                    "leave_ts": None,
                    "stay_sec": None
                }
                await send_join_log(client, channel_name, member, now_ts)
                asyncio.create_task(speak_in_channel(ch, f"{member.display_name}さんが入室しました"))

            # 退出
            for member in last_members - current_members:
                if member.bot:
                    continue
                print(f"📤 退出: {member.display_name}")
                rec = active_channels[channel_id]["member_records"].get(member.id)
                if rec and rec["leave_ts"] is None:
                    leave_ts = datetime.now(JST).timestamp()
                    stay_sec = int(leave_ts - rec["join_ts"])
                    rec["leave_ts"] = leave_ts
                    rec["stay_sec"] = stay_sec
                    await send_leave_log(client, channel_name, member, leave_ts, stay_sec)
                    asyncio.create_task(speak_in_channel(ch, f"{member.display_name}さんが退出しました"))

            last_members = current_members

            # 0人になったら5秒待って削除
            if len(current_members) == 0:
                print(f"👥 0人になりました → 5秒後に削除します")
                await asyncio.sleep(TIMEOUT_EMPTY)
                ch = client.get_channel(channel_id)
                if ch and len(ch.members) == 0:
                    records = list(active_channels[channel_id]["member_records"].values())
                    await send_delete_summary_log(client, channel_name, "誰もいなくなったため自動削除", records)
                    for vc in client.voice_clients:
                        if vc.channel and vc.channel.id == channel_id:
                            await vc.disconnect()
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
                default="⬇️のボタンを押すと通話チャンネルが作成できます。作成者の方は2分以内に入室してください。誰も入らないと自動削除されます。全員退出後5秒でチャンネル削除になります。",
                style=discord.TextStyle.long,
                required=True
            )

            async def on_submit(self, m_itx: discord.Interaction):
                await m_itx.response.defer(ephemeral=True)
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
        description="⬇️のボタンを押すと通話チャンネルが作成できます。作成者の方は2分以内に入室してください。誰も入らないと自動削除されます。全員退出後5秒でチャンネル削除になります。",
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
